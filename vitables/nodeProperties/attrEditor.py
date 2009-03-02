#!/usr/bin/env python
# -*- coding: utf-8 -*-


#       Copyright (C) 2005, 2006, 2007 Carabos Coop. V. All rights reserved
#       Copyright (C) 2008, 2009 Vicent Mas. All rights reserved
#
#       This program is free software: you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation, either version 3 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#       Author:  Vicent Mas - vmas@vitables.org

"""
Here is defined the AttrEditor class.

Classes:

* AttrEditor(object)

Methods:

* __init__(self, asi, title, user_table)
* __tr(self, source, comment=None)
* checkAttributes(self)
* setAttributes(self)

Functions:

* checkOverflow(dtype, str_value)
* checkSyntax(value)
* formatStrValue(dtype, str_value)

Misc variables:

* __docformat__

"""

__docformat__ = 'restructuredtext'

import sets

import numpy

from PyQt4.QtGui import *


import vitables.utils

def checkSyntax(value):
    """Check the syntax of a `Python` expression.

    :Parameters value: the Python expression to be evaluated
    """

    if value[0] in ("'", '"'):
        # Quotes are not permitted in the first position
        return False
    try:
        eval(value)
    except:
        return False
    else:
        return True


def formatStrValue(dtype, str_value):
    """
    Format the string representation of a value accordingly to its data type.
    
    :Parameters:

    - dtype: the value data type
    - str_value: the string representation of a value
    """

    try:
        if dtype == u'bool':
            # Every listed value is valid but none of them would
            # pass the out of range test later so we use a fake
            # valid value.
            # Beware that numpy.array(True).astype('bool')[()] fails
            # with a TypeError so we use '1' as a fake value
            if str_value in [u'1', u'TRUE', u'True', u'true']:
                str_value = u'1'
            elif str_value in [u'0', u'FALSE', u'False', u'false']:
                str_value = u'0'
            else:
                raise TypeError
        elif dtype.startswith(u'complex'):
            # Valid complex literal strings do not have parenthesis
            if str_value.startswith(u'(') and str_value.endswith(u')'):
                str_value = str_value[1:-1]
    except TypeError:
        return None
    else:
        return str_value


def checkOverflow(dtype, str_value):
    """
    Check for overflows in integer and float values.

    By default, when overflow occurs in the creation of a numpy array,
    it is silently converted to the desired data type:

    >>> numpy.array(-4).astype(numpy.uint8)
    array(252, dtype=uint8)
    >>> numpy.array(1420).astype(numpy.int8)
    array(-116, dtype=int8)

    This behavior can be acceptable for a library, but not for an end
    user application as ViTables so we have to catch such cases.

    :Parameters:

    - dtype: the value data type
    - str_value: the string representation of a value
    """

    dtypes_map = {
        u'int8': numpy.int8, u'int16': numpy.int16,
        u'int32': numpy.int32, u'int64': numpy.int64,
        u'uint8': numpy.uint8, u'uint16': numpy.uint16,
        u'uint32': numpy.uint32, u'uint64': numpy.uint64,
        u'float32': numpy.float32, u'float64': numpy.float64,
        }

    if dtype not in dtypes_map:
        return str_value

    if dtype.startswith(u'float'):
        max_value = numpy.finfo(dtypes_map[dtype]).max
        min_value = numpy.finfo(dtypes_map[dtype]).min
        value = float(str_value)
    else:
        max_value = numpy.iinfo(dtypes_map[dtype]).max
        min_value = numpy.iinfo(dtypes_map[dtype]).min
        value = long(str_value)

    if value < min_value or value > max_value:
        raise ValueError
    else:
        return str_value


class AttrEditor(object):
    """
    Setup the attributes entered in the Properties dialog.

    When the user edits the Attributes Set Instance (see PyTables manual
    for details) of a given node via the Properties dialog and presses OK
    the validity of the new set of attributes is checked. If it is OK
    then the old ASI is replaced by the new one and the dialog is closed.
    If an error is found in the new set of attributes then the dialog
    remains opened until the user fixes the mistake.
    """

    def __init__(self, asi, title, user_table):
        """:Parameters:

        - `asi`: the Attributes Set Instance being updated
        - `title`: the TITLE attribute entered by the user in the Properties dialog
        - `user_table`: the table of user attributes edited by the user in the Properties dialog
        """

        self.asi = asi

        # A dictionary with the attributes that have to be checked
        self.edited_attrs = {}
        model = user_table.model()
        rows = model.rowCount()
        # Parse the table and get string representations of its cell contents
        for row in range(0, rows):
            # As ViTables doesn't support editing ND-array attributes they
            # are marked in order to be found later
            name_item = model.item(row, 0)
            if not name_item.isEditable():
                multidim = True
            else:
                multidim = False
            name = unicode(model.item(row, 0).text())
            value = unicode(model.item(row, 1).text())
            dtype_index = model.indexFromItem(model.item(row, 2))
            current_dtype = user_table.indexWidget(dtype_index).currentText() 
            dtype = unicode(current_dtype)
            self.edited_attrs[row] = (name, value, dtype, multidim)

        # Add the TITLE attribute to the dictionary
        if title is not None:
            self.edited_attrs[rows] = (u'TITLE', title, u'string', False)


    def __tr(self, source, comment=None):
        """Translate method."""
        return unicode(qApp.translate('AttrEditor', source, comment))


    def checkAttributes(self):
        """
        Check the user attributes table.

        If empty or repeated names, values mismatching the
        attribute type or out of range values are found then nothing
        is done. If the table is OK the node `ASI` is updated and the
        Properties dialog is closed.
        """

        # Error message for mismatching value/type pairs
        dtype_error = self.__tr("""\nError: "%s" value """
            """mismatches its data type.""",
            'User attributes table editing error')

        # Error message for out of range values
        range_error = self.__tr("""\nError: "%s" value """
            """is out of range.""",
            'User attributes table editing error')

        # Error message for syntax errors in Python attributes
        syntax_error = self.__tr("""\nError: "%s" """
            """cannot be converted to a Python object.""",
            'User attributes table editing error')

        rows_range = self.edited_attrs.keys()

        # Check for empty Name cells
        for row in rows_range:
            name = self.edited_attrs[row][0]
            # Empty Value cells are acceptable for string attributes
            # but empty Name cells are invalid
            if name == u'':
                return (False, 
                        self.__tr("\nError: empty field Name in the row %i", 
                        'User attributes table editing error') % int(row + 1))

        # Check for repeated names
        names_list = []
        for row in rows_range:
            name = self.edited_attrs[row][0]
            if not name in names_list:
                names_list.append(name)
            else:
                return (False, 
                        self.__tr('\nError: attribute name "%s" is repeated.', 
                        'User attributes table editing error') % name)

        # Check for dtype, range and syntax correctness of scalar attributes
        for row in rows_range:
            name, value, dtype, multidim = self.edited_attrs[row]
            if multidim == True:
                continue
            if dtype == 'python':
                # Check the syntax of the Python expression
                if not checkSyntax(value):
                    return (False, syntax_error % name)
            else:
                # Format properly the string representation of value
                value = formatStrValue(dtype, value)
                if value is None :
                    return (False, dtype_error % name)
                # Check if values are out of range
                else:
                    try:
                        value = checkOverflow(dtype, value)
                        # astype() doesn't support unicode arguments
                        dtype_enc = dtype.encode('utf_8')
                        numpy.array(value).astype(dtype_enc)[()]
                    except IndexError:
                        return (False, range_error % name)
                    except ValueError:
                        return (False, dtype_error % name)

            # If the attribute passes every test then its entry in the
            # dictionary of edited attributes is updated
            self.edited_attrs[row] = name, value, dtype, multidim

        return (True, None)


    def setAttributes(self):
        """
        Update edited attributes.

        If the user attributes have been edited the attribute set instance
        of the node being inspected must be updated.
        """

        # Get rid of deleted attributes
        if self.edited_attrs.has_key(u'TITLE'):
            all_attrs = sets.Set(self.asi._v_attrnamesuser + [u"TITLE"])
        else:
            all_attrs = sets.Set(self.asi._v_attrnamesuser)
        edited_attrs_names = sets.Set([self.edited_attrs[row][0] 
                                        for row in self.edited_attrs.keys()])
        for attr in (all_attrs - edited_attrs_names):
            try:
                self.asi._v_node._f_delAttr(attr)
            except:
                vitables.utils.formatExceptionInfo()

        for row in self.edited_attrs.keys():
            # Scalar attributes are stored as
            # numpy scalar arrays of the proper type
            name, value, dtype, multidim = self.edited_attrs[row]
            if multidim == True:
                continue

            if dtype == u'python':
                value = eval(u'%s' % value)
            else:
                dtype_enc = dtype.encode('utf_8')
                value = numpy.array(value).astype(dtype_enc)[()]

            # Updates the ASI
            try:
                setattr(self.asi, name, value)
            except:
                vitables.utils.formatExceptionInfo()

