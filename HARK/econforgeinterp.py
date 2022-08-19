from HARK.core import MetricObject
from interpolation.splines import eval_linear, eval_spline, CGrid
from interpolation.splines import extrap_options as xto

import numpy as np
from copy import copy

extrap_opts = {
    "linear": xto.LINEAR,
    "nearest": xto.NEAREST,
    "constant": xto.CONSTANT,
}


class LinearFast(MetricObject):
    """
    A class that constructs and holds all the necessary elements to
    call a multilinear interpolator from econforge.interpolator in
    a way that resembles the basic interpolators in HARK.interpolation.
    """

    distance_criteria = ["f_val", "grid_list"]

    def __init__(self, f_val, grids, extrap_mode="linear"):
        """
        f_val: numpy.array
            An array containing the values of the function at the grid points.
            It's i-th dimension must be of the same lenght as the i-th grid.
            f_val[i,j,k] must be f(grids[0][i], grids[1][j], grids[2][k]).
        grids: [numpy.array]
            One-dimensional list of numpy arrays. It's i-th entry must be the grid
            to be used for the i-th independent variable.
        extrap_mode: one of 'linear', 'nearest', or 'constant'
            Determines how to extrapolate, using either nearest point, multilinear, or 
            constant extrapolation. The default is multilinear.
        """
        self.dim = len(grids)
        self.f_val = f_val
        self.grid_list = grids
        self.Grid = CGrid(*grids)

        # Set up extrapolation options
        self.extrap_mode = extrap_mode
        try:
            self.extrap_options = extrap_opts[self.extrap_mode]
        except KeyError:
            raise KeyError(
                'extrap_mode must be one of "linear", "nearest", or "costant"'
            )

    def __call__(self, *args):
        """
        Calls the interpolator.
        
        args: [numpy.array]
            List of arrays. The i-th entry contains the i-th coordinate
            of all the points to be evaluated. All entries must have the
            same shape.
        """
        array_args = [np.asarray(x) for x in args]

        # Call the econforge function
        f = eval_linear(
            self.Grid,
            self.f_val,
            np.column_stack([x.flatten() for x in array_args]),
            self.extrap_options,
        )

        # Reshape the output to the shape of inputs
        return np.reshape(f, array_args[0].shape)

    def _derivs(self, deriv_tuple, *args):
        """
        Evaluates derivatives of the interpolator.

        Parameters
        ----------
        deriv_tuple : tuple of tuples of int
            Indicates what are the derivatives to be computed.
            It follows econforge's notation, where a derivative
            to be calculated is a tuple of length equal to the
            number of dimensions of the interpolator and entries
            in that tuple represent the order of the derivative.
            E.g. to calculate f(x,y) and df/dy(x,y) use
            deriv_tuple = ((0,0),(0,1))

        args: [numpy.array]
            List of arrays. The i-th entry contains the i-th coordinate
            of all the points to be evaluated. All entries must have the
            same shape.

        Returns
        -------
        [numpy.array]
            List of the derivatives that were requested in the same order
            as deriv_tuple. Each element has the shape of items in args.
        """

        # Format arguments
        array_args = [np.asarray(x) for x in args]

        # Find derivatives with respect to every dimension
        derivs = eval_spline(
            self.Grid,
            self.f_val,
            np.column_stack([x.flatten() for x in array_args]),
            out=None,
            order=1,
            diff=str(deriv_tuple),
            extrap_mode=self.extrap_mode,
        )

        # Reshape
        derivs = [derivs[:, j].reshape(args[0].shape) for j in range(self.dim)]

        return derivs

    def gradient(self, *args):
        """
        Evaluates gradient of the interpolator.

        Parameters
        ----------
        args: [numpy.array]
            List of arrays. The i-th entry contains the i-th coordinate
            of all the points to be evaluated. All entries must have the
            same shape.

        Returns
        -------
        [numpy.array]
            List of the derivatives of the function with respect to each
            input, evaluated at the given points. E.g. if the interpolator
            represents 3D function f, f.gradient(x,y,z) will return
            [df/dx(x,y,z), df/dy(x,y,z), df/dz(x,y,z)]. Each element has the
            shape of items in args.
        """
        # Form a tuple that indicates which derivatives to get
        # in the way eval_linear expects
        deriv_tup = tuple(
            tuple(1 if j == i else 0 for j in range(self.dim)) for i in range(self.dim)
        )

        return self._derivs(deriv_tup, *args)

    def _eval_and_grad(self, *args):
        """
        Evaluates interpolator and its gradient.

        Parameters
        ----------
        args: [numpy.array]
            List of arrays. The i-th entry contains the i-th coordinate
            of all the points to be evaluated. All entries must have the
            same shape.

        Returns
        -------
        numpy.array
            Value of the interpolator at given arguments.
        [numpy.array]
            List of the derivatives of the function with respect to each
            input, evaluated at the given points. E.g. if the interpolator
            represents 3D function f, the list will be
            [df/dx(x,y,z), df/dy(x,y,z), df/dz(x,y,z)]. Each element has the
            shape of items in args.
        """
        # (0,0,...,0) to get the function evaluation
        eval_tup = tuple([tuple(0 for i in range(self.dim))])

        # Tuple with indicators for all the derivatives
        deriv_tup = tuple(
            tuple(1 if j == i else 0 for j in range(self.dim)) for i in range(self.dim)
        )

        results = self._derivs(eval_tup + deriv_tup, *args)

        return (results[0], results[1:])