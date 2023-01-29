"""
Helper classes to build and store clause logic for queries.
"""

# System Imports.
import datetime, re
from io import StringIO
from tokenize import (
    generate_tokens,
    ENDMARKER,
    NAME,
    NEWLINE,
    NUMBER,
    OP,
    STRING,
)


class BaseClauseBuilder(object):
    """"""
    def __init__(self, validation_class, clause_type, *args, **kwargs):
        # Call parent logic.
        super().__init__(*args, **kwargs)

        # Validate clause type.
        self._clause_type = str(clause_type).lower().strip()
        valid_clause_types = {
            'select': None,
            'where': None,
            'columns': None,
            'values': None,
            'order_by': None,
        }
        try:
            valid_clause_types[self._clause_type]
        except KeyError:
            raise ValueError('Invalid clause type of "{0}".'.format(clause_type))

        # Initialize values.
        self._parent = validation_class
        self._base = validation_class._base
        self._clause_array = []
        self._sanitized_clause = None
        self._print_parens = True
        self._always_quote = True
        self._allow_spaces = False

    def __str__(self):
        if len(self.array) > 0:
            # Non-empty clause. Format for str output.
            to_str = ', '.join('{}' for x in range(len(self.array)))
            to_str = to_str.format(*self.array)
            if self._print_parens:
                to_str = '{0}({1})'.format(self._print_prefix, to_str)
            else:
                to_str = '{0}{1}'.format(self._print_prefix, to_str)
            return to_str
        else:
            # Empty clause.
            return ''

    def __repr__(self):
        return str(tuple(self._clause_array))

    def __len__(self):
        return len(self.__str__())

    def __iter__(self):
        return iter(self.__str__())

    def split(self, *args, **kwargs):
        return self.__str__().split(*args, **kwargs)

    @property
    def array(self):
        return self._clause_array

    @array.setter
    def array(self, value):
        self._to_array(value)

    @property
    def context(self):
        if len(self.array) > 0:
            context = ', '.join('%s' for i in range(len(self.array)))
            return context
        else:
            return ''

    @property
    def data(self):
        single_depth_array = []
        for index in range(len(self.array)):
            single_depth_array.append(self.array[index])

        return single_depth_array

    def _to_array(self, value):
        """Converts clause to array format for initial parsing."""
        if self._clause_prefix is None:
            raise NotImplementedError('Query type {0} missing clause_prefix value.'.format(self.__class__))
        if self._print_prefix is None:
            raise NotImplementedError('Query type {0} missing print_prefix value.'.format(self.__class__))
        if self._quote_format is None:
            raise NotImplementedError('Query type {0} missing quote_format value.'.format(self.__class__))

        print('')
        print('original val: {0}'.format(value))

        if isinstance(value, list):
            # Already list format.
            clause = value
        elif isinstance(value, tuple):
            # Close to list format. Simply convert.
            clause = list(value)
        else:
            # Attempt to parse as str for all other formats.
            if value is None:
                # None type defaults to empty.
                clause = []
            else:
                clause = str(value).strip()

                # Trim prefix, if present.
                if len(self._clause_prefix) > 0:
                    # Check if starts with prefix, brackets, and space.
                    if (
                        clause.upper().startswith('{0} ('.format(self._clause_prefix)) and clause.endswith(')')
                        or clause.upper().startswith('{0} ['.format(self._clause_prefix)) and clause.endswith(']')
                    ):
                        clause = clause[(len(self._clause_prefix) + 2):-1]

                    # Check if starts with prefix, brackets, and no space.
                    elif (
                        clause.upper().startswith('{0}('.format(self._clause_prefix)) and clause.endswith(')')
                        or clause.upper().startswith('{0}['.format(self._clause_prefix)) and clause.endswith(']')
                    ):
                        clause = clause[(len(self._clause_prefix) + 1):-1]

                    # Check if starts with prefix and no brackets.
                    elif clause.upper().startswith('{0} '.format(self._clause_prefix)):
                        clause = clause[(len(self._clause_prefix) + 1):]

                    # Check if starts with brackets only and no prefix.
                    elif (
                        clause.startswith('(') and clause.endswith(')')
                        or clause.startswith('[') and clause.endswith(']')
                    ):
                        clause = clause[1:-1]

                # Convert to list.
                clause = clause.split(',')
                for index in range(len(clause)):
                    clause[index] = str(clause[index]).strip()

                # Remove potential trailing deadspace.
                if len(clause) > 1 and clause[-1] == '':
                    clause = clause[:-1]

        # Validate each item in clause, now that it's an array.
        if len(clause) == 1 and clause[0] == '*':
            # Save wildcard clause.
            self._clause_array = ['*']

        elif len(clause) > 0:
            # Handle any other clause that is non-empty.
            clause = self._validate_clause(clause)

            # Save validated clause.
            self._clause_array = clause
        else:
            # Save empty clause.
            self._clause_array = []

    def _validate_clause(self, original_clause):
        """Used to validate/sanitize an array of clause values."""
        new_clause = []
        for item in original_clause:

            # Handle various specific types.
            is_datetime = False
            if isinstance(item, datetime.datetime):
                # Is a datetime object. Convert to string.
                item = "'{0}'".format(item.strftime('%Y-%m-%d %H:%M:%S'))
                is_datetime = True

            elif isinstance(item, datetime.date):
                # Is a date object. Convert to string.
                item = "'{0}'".format(item.strftime('%Y-%m-%d'))
                is_datetime = True

            # Skip handling for other non-str items.
            elif not isinstance(item, str):
                new_clause.append(item)
                continue

            # If we made it this far, then item is a str (or converted to such).
            item = str(item).strip()

            # Strip out function values.
            # First check against regex matches.
            func_call_regex = (r'\(*|'.join(self._parent._reserved_function_names))
            matches = re.match(func_call_regex, item, flags=re.IGNORECASE)

            # Proceed if at least one match is found.
            stripped_left = ''
            stripped_right = ''
            if matches:
                index = 0
                while index < len(self._parent._reserved_function_names):
                    func_call = self._parent._reserved_function_names[index]
                    if (
                        re.match(r'^{0}\('.format(func_call), item, flags=re.IGNORECASE)
                        and item[-1] == ')'
                    ):
                        # Found a match. Update identifier and check for further matches.
                        length = len(func_call) + 1
                        stripped_left += item[:length]
                        stripped_right += ')'
                        item = item[length:-1].strip()
                    index += 1

            # Ignore potential type casting syntax.
            cast_identifier = ''
            if self._base._config.db_type == 'PostgreSQL':
                # Handle for PostgreSQL casting.
                cast_split = item.split('::')
                if len(cast_split) > 2:
                    raise ValueError('Invalid casting identifier "{0}"'.format(item))
                elif len(cast_split) > 1:
                    cast_identifier = cast_split[1]
                    if not re.match(r'[A-Za-z0-9]+', cast_identifier):
                        raise ValueError('Invalid casting identifier "{0}"'.format(cast_identifier))
                    cast_identifier = '::{0}'.format(cast_identifier)
                item = cast_split[0]

            # Validate individual identifier.
            order_by_descriptor = ''
            if item != '*':
                # To check identifier, trim possible ASC/DESC values.
                if item.lower().endswith(' asc'):
                    # Handle for ASC syntax.
                    item = item[:-4].rstrip()
                    order_by_descriptor = ' ASC'
                if item.lower().endswith(' desc'):
                    # Handle for DESC syntax.
                    item = item[:-5].rstrip()
                    order_by_descriptor = ' DESC'

            # # Extra string handling for date/datetime objects.
            # if is_datetime:
            #     item = item[1:-1]

            print('')
            print('item: {0}'.format(item))

            # if (
            #     len(item) > 0
            #     and item != '*'
            #     and (
            #         item[0] not in ['"', "'", '`']
            #         or item[-1] not in ['"', "'", '`']
            #     )
            # ):
            #     item = """'{0}'""".format(item)

            # # Check if apostrophe in value.
            # if "'" in item:
            #     print('\n\n\n\n')
            #     print('replacing quote in {0}'.format(item))
            #     item.replace("'", '\0027')
            #     print('replaced quote in {0}'.format(item))

            # If we made it this far, item is valid. Escape with proper quote format and readd.
            is_quoted = False
            if self.is_quoted(item):
                item = item[1:-1].strip()
                is_quoted = True

            # Skip items that are empty. Otherwise append.
            if len(item) > 0:
                print('')
                print('item: {0}'.format(item))
                print('is_quoted: {0}'.format(is_quoted))
                if item != '*':
                    # Readd quotes in proper format.
                    # Account for statements that may have multiple parts (denoted by spaces).
                    if not self._allow_spaces:
                        item_split = item.split(' ')
                        if self._always_quote or is_quoted:
                            item = '{1}{0}{1}'.format(item_split.pop(0), self._quote_format)
                        while len(item_split) > 0:
                            item_split_part = item_split.pop(0).strip()
                            if len(item_split_part) > 0:
                                item = '{0} {1}'.format(item, item_split_part)
                    else:
                        if self._always_quote or is_quoted:
                            item = '{1}{0}{1}'.format(item, self._quote_format)

                # Readd identifiers in proper format.
                item = '{0}{1}{2}'.format(item, cast_identifier, order_by_descriptor)

                # Readd function calls if present.
                item = '{1}{0}{2}'.format(item, stripped_left.upper(), stripped_right)

                # Save item to clause.
                new_clause.append(item)

        print('final result: {0}'.format(item))

        return new_clause

    @staticmethod
    def is_quoted(value):
        """Checks if provided value is quoted.

        Aka, these are three "quoted" values: "id", `first_name`, 'last_name'
        These are not "quoted" values:
            id, first_name, last_name
            "id'
            'id"
            `id'
            etc...
        """
        is_quoted = False
        if isinstance(value, str):
            # Only attempt to check if str type.
            value = value.strip()

            # Must have matching outer quotes, plus at least one inner character.
            if len(value) > 2 and value[0] == value[-1] and value[0] in ['`', '"', "'"]:
                is_quoted = True

        return is_quoted


class SelectClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='SELECT', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = ''
        self._print_prefix = ''
        self._quote_format = '"'

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Process and save provided clause.
        self.array = clause

    def __str__(self):
        # Handle for all-star return.
        if len(self.array) == 1 and self.array[0] == '*':
            return '*'

        # Handle for all other values.
        return super().__str__()

    def _to_array(self, value):
        # If none, set to all-star.
        if value is None:
            value = ['*']

        # Call parent logic.
        super()._to_array(value)

        # If validation returned empty set, set to all-star.
        if len(self.array) == 0:
            self.array = ['*']

        # Error if wildcard star used with any other values.
        elif len(self.array) > 1 and '*' in self.array:
            raise ValueError('SELECT clause provided * with other params. * is only valid alone.')


class WhereClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='WHERE', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = 'WHERE'
        self._print_prefix = 'WHERE '
        self._quote_format = '"'

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Process and save provided clause.
        self.array = clause

    def __str__(self):
        if len(self.array) > 0:
            # Non-empty clause. Format for str output.
            to_str = ''
            temp_array = self.array
            for value in self._clause_connectors:
                if value == []:
                    to_str += '({0})'.format(temp_array.pop(0))
                else:
                    to_str += ' {0} '.format(value)

            to_str = '\n{0}{1}'.format(self._print_prefix, to_str)
            return to_str
        else:
            # Empty clause.
            return ''

    def _to_array(self, value):
        """Converts clause to array format for initial parsing."""
        self._clause_connectors = []

        if self._clause_prefix is None:
            raise NotImplementedError('Query type {0} missing clause_prefix value.'.format(self.__class__))
        if self._quote_format is None:
            raise NotImplementedError('Query type {0} missing quote_format value.'.format(self.__class__))

        # First parse initial expected types.
        if isinstance(value, list) or isinstance(value, tuple):
            # In list or tuple format. For consistent tokenization, convert to str.
            new_value = ''
            for item in value:

                # # By default, combine all individual values with AND operators.
                # # Skip this for the first index, as there's nothing to combine yet.
                if len(new_value) > 0:
                    new_value += ' AND '

                # Add current item to str.
                new_value += item

            # Save formatted string.
            value = new_value

        # Parse
        if value is None or value.strip() == '':
            # None type and empty clauses default to empty.
            clause = []
        else:
            clause = str(value).strip()

            # Trim prefix, if present.
            if len(self._clause_prefix) > 0:
                # Check if starts with prefix, brackets, and space.
                if (
                    clause.upper().startswith('{0} ('.format(self._clause_prefix)) and clause.endswith(')')
                    or clause.upper().startswith('{0} ['.format(self._clause_prefix)) and clause.endswith(']')
                ):
                    clause = clause[(len(self._clause_prefix) + 2):-1]

                # Check if starts with prefix, brackets, and no space.
                elif (
                    clause.upper().startswith('{0}('.format(self._clause_prefix)) and clause.endswith(')')
                    or clause.upper().startswith('{0}['.format(self._clause_prefix)) and clause.endswith(']')
                ):
                    clause = clause[(len(self._clause_prefix) + 1):-1]

                # Check if starts with prefix and no brackets.
                elif clause.upper().startswith('{0} '.format(self._clause_prefix)):
                    clause = clause[(len(self._clause_prefix) + 1):]

            clause = self.tokenize_value(clause)

        # Validate each item in clause, now that it's an array.
        if len(clause) > 0:

            # Loop through each clause item. Correct quotes.
            # TODO: For now, we assume that the first item (separated by spaces) will always be a column.
            #  Fix this logic later.
            for index in range(len(clause)):
                clause_item = clause[index]

                # Split based on spaces. For now, we assume only the first item needs quotes.
                clause_split = clause_item.split(' ')
                first_item = clause_split[0]
                if self.is_quoted(first_item):
                    first_item = first_item[1:-1]
                first_item = '{1}{0}{1}'.format(first_item, self._quote_format)

                # Recombine into single string.
                clause_split[0] = first_item
                clause[index] = ' '.join(clause_split)

            # Save validated clause.
            self._clause_array = clause
        else:
            # Save empty clause.
            self._clause_array = []
            self._clause_connectors = []

    def tokenize_value(self, value):
        """"""
        print('\n\n\n\n')
        print('clause:')
        print('{0}'.format(value))
        print('\n')
        tokens = list(generate_tokens(StringIO(value).readline))
        print('\nas tokens:')

        for token in tokens:
            token.actual_start = tuple(token.start)
            token.actual_end = tuple(token.end)
            token.actual_string = token.string

        section_str = ''
        sub_section_str = ''
        token_set = []
        index = 0
        curr_line_start = 1
        curr_line_end = 1
        curr_index_start = 0
        curr_index_end = 0
        prev_line_start = 0
        prev_line_end = 0
        prev_index_start = 0
        prev_index_end = 0
        prev_prev_index_end = 0
        while index < len(tokens):
            print('')
            keep_index = False
            token = tokens[index]

            # Process if handling a subsection.
            if sub_section_str != '':
                sub_section_str += token.actual_string

                # Check if end of subsection.
                if token == ')':
                    print('        Finishing subsection.')
                    # End of subsection. Recursively call to process.
                    # sub_clause = self._tokenize_value(sub_section_str)

                    # Clear out subsection holder.
                    sub_section_str = ''

            # If inner parens exist, then we need to recursively call to process sub-section.
            # First we start building our sub-string to process.
            if token == '(':
                print('        Handling subsection.')

                # Update index trackers.
                prev_line_start = curr_line_start
                prev_index_start = curr_index_start
                prev_line_end = curr_line_end
                prev_prev_index_end = prev_index_end
                prev_index_end = curr_index_end
                curr_line_start = token.actual_start[0]
                curr_line_end = token.actual_end[0]
                curr_index_start = token.actual_start[1]
                curr_index_end = token.actual_end[1]

                # Handle for when tokenizer skips/ignores spaces.
                section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str)

                # Save value.
                sub_section_str += token.actual_string

            # Not processing sub-section.
            # Determine if token is AND or OR.
            elif token.type == 1 and token.actual_string.upper() in ['AND', 'OR']:
                # Token is AND or OR combiner. Handle appropriately.
                print('        Handling combiner.')

                # Update index trackers.
                prev_line_start = curr_line_start
                prev_index_start = curr_index_start
                prev_line_end = curr_line_end
                prev_prev_index_end = prev_index_end
                prev_index_end = curr_index_end
                curr_line_start = token.actual_start[0]
                curr_line_end = token.actual_end[0]
                curr_index_start = token.actual_start[1]
                curr_index_end = token.actual_end[1]

                # Handle for when tokenizer skips/ignores spaces.
                section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str).strip()

                # Trim trailing final paren, if present.
                if len(section_str) > 1 and section_str[-1] in [')', ']']:
                    section_str = section_str[:-1]

                # Save our currently assembled section of tokens.
                token_set.append(section_str.strip())

                # Append our found combiner token.
                self._clause_connectors.append([])
                self._clause_connectors.append(token.actual_string.upper())

                # Clear out saved section, for further processing.
                section_str = ''

            # For all other token types, assume is part of current section. Append to existing section.
            else:

                # To account for special tokenization edge-cases, we recursively check str types when applicable.
                if token.type == 3:

                    # Update index trackers.
                    prev_line_start = curr_line_start
                    prev_index_start = curr_index_start
                    prev_line_end = curr_line_end
                    prev_prev_index_end = prev_index_end
                    prev_index_end = curr_index_end
                    curr_line_start = token.actual_start[0]
                    curr_line_end = token.actual_end[0]
                    curr_index_start = token.actual_start[1]
                    curr_index_end = token.actual_end[1]

                    # Handle for when tokenizer skips/ignores spaces.
                    section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str)

                    # Re-parse as a sub-token set.
                    re_parsed_set = self._tokenize_edge_case_str(
                        token.actual_string,
                        curr_line_start,
                        curr_line_end,
                        curr_index_start,
                        curr_index_end,
                    )

                    # Take re-parsed sub-token set. Append to current location in token set.
                    curr_index = index
                    print('curr_index: {0}'.format(curr_index))
                    orig_tokens_left = list(tokens[:curr_index])
                    orig_tokens_right = list(tokens[(curr_index + 1):])
                    print('    left:')
                    for left_token in orig_tokens_left:
                        print('        {0}'.format(left_token))
                    print('    right:')
                    for right_token in orig_tokens_right:
                        print('        {0}'.format(right_token))

                    new_token_set = orig_tokens_left + re_parsed_set + orig_tokens_right
                    print('\n')
                    print('new_token_set:')
                    for new_token in new_token_set:
                        print('    Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                            new_token.type,
                            new_token.actual_string,
                            new_token.actual_start,
                            new_token.actual_end,
                        ))
                    print('\n\n')

                    tokens = new_token_set

                    # Record that we HAVE NOT fully handled current index yet.
                    keep_index = True

                # Certain types need string spacing.
                elif token.type in [1, 2]:
                    # Standard string types.
                    print('        Handling string token.')

                    # Update index trackers.
                    prev_line_start = curr_line_start
                    prev_index_start = curr_index_start
                    prev_line_end = curr_line_end
                    prev_prev_index_end = prev_index_end
                    prev_index_end = curr_index_end
                    curr_line_start = token.actual_start[0]
                    curr_line_end = token.actual_end[0]
                    curr_index_start = token.actual_start[1]
                    curr_index_end = token.actual_end[1]

                    # Handle for when tokenizer skips/ignores spaces.
                    section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str)

                    # Save token value.
                    section_str += '{0}'.format(token.actual_string)

                elif token.type in [54]:
                    # Operator types, such as equals sign.
                    print('        Handling operator token.')

                    # Update index trackers.
                    prev_line_start = curr_line_start
                    prev_index_start = curr_index_start
                    prev_line_end = curr_line_end
                    prev_prev_index_end = prev_index_end
                    prev_index_end = curr_index_end
                    curr_line_start = token.actual_start[0]
                    curr_line_end = token.actual_end[0]
                    curr_index_start = token.actual_start[1]
                    curr_index_end = token.actual_end[1]

                    # Handle for when tokenizer skips/ignores spaces.
                    section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str)

                    # Skip parens if first value in section.
                    if not (token.actual_string in ['(', '['] and section_str.strip() == ''):
                        section_str += '{0}'.format(token.actual_string)

                else:
                    # All other types. Append as-is.
                    print('        Handling generic token.')

                    # Update index trackers.
                    prev_line_start = curr_line_start
                    prev_index_start = curr_index_start
                    prev_line_end = curr_line_end
                    prev_prev_index_end = prev_index_end
                    prev_index_end = curr_index_end
                    curr_line_start = token.actual_start[0]
                    curr_line_end = token.actual_end[0]
                    curr_index_start = token.actual_start[1]
                    curr_index_end = token.actual_end[1]

                    # Handle for when tokenizer skips/ignores spaces.
                    section_str = self._tokenize_handle_space(curr_index_start, prev_index_end, section_str)

                    # Save value.
                    section_str += token.actual_string

            print('        section_str: {0}'.format(section_str))

            if not keep_index:
                index += 1

                print('        Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                    token.type,
                    token.actual_string,
                    token.actual_start,
                    token.actual_end,
                ))

        # Done with loops. Do final post-processing.
        # Trim trailing final paren, if present.
        if len(section_str) > 1 and section_str[-1] in [')', ']']:
            section_str = section_str[:-1]

        # Save our last-handled section, if any.
        if section_str.strip() != '':
            self._clause_connectors.append([])
            token_set.append(section_str.strip())

        # Double check expected location.
        temp = value.split('\n')
        temp.append('')
        if curr_line_end != len(temp):

            print('curr_line_end: {0}'.format(curr_line_end))
            print('len(temp): {0}'.format(len(temp)))

            print('Final token_set:')
            for token in token_set:
                print('    {0}'.format(token))
                # print('    Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                #     token.type,
                #     token.actual_string,
                #     token.actual_start,
                #     token.actual_end,
                # ))

            raise ValueError('Error parsing array indexes. Failed at line parsing.')
        if prev_index_end != len(value.replace('\n', '')) + 1:

            print('curr_index_end: {0}'.format(curr_index_end))
            print('prev_index_end: {0}'.format(prev_index_end))
            print('prev_prev_index_end: {0}'.format(prev_prev_index_end))
            print('len(value): {0}'.format(len(value.replace('\n', '')) + 1))

            print('Final token_set:')
            print('{0}'.format(token_set))
            for token in token_set:
                print('    {0}'.format(token))
                # print('    Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                #     token.type,
                #     token.actual_string,
                #     token.actual_start,
                #     token.actual_end,
                # ))

            raise ValueError('Error parsing array indexes. Failed at index parsing.')

        print('\n')
        print('final self._clause_connectors:')
        print('{0}'.format(self._clause_connectors))
        print('')
        print('final token_set:')
        print('{0}'.format(token_set))
        print('\n\n\n\n')

        return token_set

    def _tokenize_handle_space(self, curr_index_start, prev_index_end, section_str):
        # Check if current index and previous index match. If not, then likely have missing space characers.
        temp_val = curr_index_start - prev_index_end
        if temp_val > 0:
            # Missing characters. Add that many space tokens.
            for x in range(temp_val):
                section_str += ' '

        # Return updated set.
        return section_str

    def _tokenize_edge_case_str(self, value, line_start, line_end, index_start, index_end):
        """"""
        print('line_start: {0}'.format(line_start))
        print('line_end: {0}'.format(line_end))
        print('index_start: {0}'.format(index_start))
        print('index_end: {0}'.format(index_end))
        curr_line = line_start
        prev_index_start = index_start
        prev_index_end = index_start + 1
        index_start += 1
        index_end -= 1
        print('')
        print('curr_line: {0}'.format(curr_line))
        print('prev_index_start: {0}'.format(prev_index_start))
        print('prev_index_end: {0}'.format(prev_index_end))
        # print('curr_index_start: {0}'.format(curr_index_start))
        # print('curr_index_end: {0}'.format(curr_index_end))

        return_set = []
        if len(value) > 0:
            # Save starting quote in str.
            start_token = list(generate_tokens(StringIO(value[0]).readline))[0]
            print('handling first index')
            start_token.actual_start = (curr_line, index_start - 1)
            start_token.actual_end = (curr_line, index_start)
            start_token.actual_string = start_token.string
            return_set.append(start_token)

            # Update for actual start.
            curr_index_start = index_start
            curr_index_end = index_start
            print('')
            print('curr_line: {0}'.format(curr_line))
            print('prev_index_start: {0}'.format(prev_index_start))
            print('prev_index_end: {0}'.format(prev_index_end))
            # print('curr_index_start: {0}'.format(curr_index_start))
            # print('curr_index_end: {0}'.format(curr_index_end))

            # Parse all inner-values (between starting and ending quote) to force standard tokenization.
            tokens = list(generate_tokens(StringIO(value[1:-1]).readline))
            for token in tokens:

                # For now, skip newlines and endmarkers. They mess up these calculations.
                if token.type in [0, 4, 6]:
                    continue

                print('')
                print('processing token: {0}'.format(token))
                # Calculate total lengths, as determined by tokenizer.
                line_length = token.end[0] - token.start[0]
                index_length = token.end[1] - token.start[1]
                if index_length < 0:
                    index_length = 0

                # Update variables for current loop.
                curr_line = curr_line + line_length
                curr_index_start = token.start[1] + index_start
                curr_index_end = curr_index_start + index_length

                print('')
                print('    curr_line: {0}'.format(curr_line))
                print('    prev_index_start: {0}'.format(prev_index_start))
                print('    prev_index_end: {0}'.format(prev_index_end))
                print('    curr_index_start: {0}'.format(curr_index_start))
                print('    curr_index_end: {0}'.format(curr_index_end))

                # Check if current index and previous index match. If not, then likely have missing space characters.
                temp_val = curr_index_start - prev_index_end
                print('    temp_val: {0}'.format(temp_val))
                if temp_val > 0:
                    # Missing characters. Add that many space tokens.

                    print('    adding spaces')
                    curr_index_start = prev_index_end
                    for x in range(temp_val):
                        space_token = list(generate_tokens(StringIO('').readline))[0]
                        space_token.actual_string = ' '
                        space_token.actual_start = (curr_line, curr_index_start)
                        curr_index_start += 1
                        space_token.actual_end = (curr_line, curr_index_start)
                        print('        Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                            space_token.type,
                            space_token.actual_string,
                            space_token.actual_start,
                            space_token.actual_end,
                        ))
                        return_set.append(space_token)

                # Generate proper token start/end locations.
                token.actual_start = (curr_line, curr_index_start)
                token.actual_end = (curr_line, curr_index_end)
                token.actual_string = token.string

                # Save token value.
                return_set.append(token)

                # Update variables for next loop.
                prev_index_start = curr_index_start
                prev_index_end = curr_index_end

                # print('')
                # print('    curr_line: {0}'.format(curr_line))
                # print('    prev_index_start: {0}'.format(prev_index_start))
                # print('    prev_index_end: {0}'.format(prev_index_end))
                # print('    curr_index_start: {0}'.format(curr_index_start))
                # print('    curr_index_end: {0}'.format(curr_index_end))

            # Double check expected location.
            if curr_line != line_end:

                print('Final return_set:')
                for token in return_set:
                    print('    Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                        token.type,
                        token.actual_string,
                        token.actual_start,
                        token.actual_end,
                    ))

                raise ValueError('Error parsing array indexes. Failed at line parsing.')
            if curr_index_end != index_end:

                while curr_index_end < index_end:
                    curr_index_start = curr_index_end
                    curr_index_end += 1
                    space_token = list(generate_tokens(StringIO('').readline))[0]
                    space_token.actual_string = ' '
                    space_token.actual_start = (curr_line, curr_index_start)
                    space_token.actual_end = (curr_line, curr_index_end)
                    print('        Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                        space_token.type,
                        space_token.actual_string,
                        space_token.actual_start,
                        space_token.actual_end,
                    ))
                    return_set.append(space_token)
                    curr_index_end += 1

                # print('')
                # print('curr_index_end: {0}'.format(curr_index_end))
                # print('prev_index_end: {0}'.format(prev_index_end))
                # print('index_end: {0}'.format(index_end))
                #
                # print('Final return_set:')
                # for token in return_set:
                #     print('    Token: (Type: {0}, String: \'{1}\', Start: {2}, End: {3}'.format(
                #         token.type,
                #         token.actual_string,
                #         token.actual_start,
                #         token.actual_end,
                #     ))
                #
                # raise ValueError('Error parsing array indexes. Failed at index parsing.')

            # Save ending quote in str.
            end_token = list(generate_tokens(StringIO(value[-1]).readline))[0]
            end_token.actual_start = (line_end, index_end)
            end_token.actual_end = (line_end, index_end + 1)
            end_token.actual_string = end_token.string
            return_set.append(end_token)

        return return_set

    def _tokenize_value(self, value):
        """Recursive inner call for "tokenize_value" function."""
        tokens = generate_tokens(StringIO(value).readline)
        for token in tokens:

            # If inner parens exist, then we need to recursively call to process sub-section.
            if token == '(':
                pass


class ColumnsClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='COLUMNS', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = 'COLUMNS'
        self._print_prefix = ''
        self._quote_format = '"'

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Process and save provided clause.
        self.array = clause

    def _to_array(self, value):
        # Call parent logic.
        super()._to_array(value)

        # Verify that wildcard star is not present.
        if '*' in self._clause_array:
            raise ValueError('The * identifier can only be used in a SELECT clause.')


class ValuesClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='VALUES', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = 'VALUES'
        self._print_prefix = 'VALUES '
        self._quote_format = "'"

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Post-parent-call initialize values.
        self._always_quote = False
        self._allow_spaces = True

        # Process and save provided clause.
        self.array = clause


class ValuesManyClauseBuilder(ValuesClauseBuilder):
    """"""

    def _validate_clause(self, original_clause):
        """Used to validate/sanitize an array of clause values."""

        # Handle the same as original logic, except there is one extra layer.
        # So loop through each inner item and hand that to validation.
        print('\n\n\n\n')
        print('original_clause:')
        print('{0}'.format(original_clause))

        if len(original_clause) > 0:
            for index in range(len(original_clause)):
                inner_clause = original_clause[index]
                print('    inner_clause:')
                print('    {0}'.format(inner_clause))
                original_clause[index] = super()._validate_clause(inner_clause)
                print('    updated inner_clause:')
                print('    {0}'.format(original_clause[index]))

            print('final result:')
            print('{0}'.format(original_clause))

            # Return validated clause.
            return original_clause

        else:
            # Return empty clause.
            return []

    def __str__(self):
        if len(self.array) > 0:
            # Non-empty clause. Format for str output.
            to_str = self.context
            all_values = []
            for inner_array in self.array:
                for value in inner_array:
                    all_values.append(value)
            print('all_values:')
            print('{0}'.format(all_values))
            print(to_str.format(*all_values))
            to_str = to_str.format(*all_values)
            print('to_str:')
            print('{0}'.format(to_str))
            if self._print_parens:
                to_str = '{0}({1})'.format(self._print_prefix, to_str)
            else:
                to_str = '{0}{1}'.format(self._print_prefix, to_str)
            return to_str
        else:
            # Empty clause.
            return ''

    @property
    def context(self):
        if len(self.array) > 0:
            context_line = ', '.join('%s' for i in range(len(self.array[0])))
            context_line = '    ({0})'.format(context_line)
            context = ',\n'.join(context_line for i in range(len(self.array)))
            context += '\n'
            return context
        else:
            return ''

    @property
    def orig_context(self):
        return super().context

    @property
    def data(self):
        single_depth_array = []
        for inner_array in self.array:
            for index in range(len(inner_array)):
                single_depth_array.append(inner_array[index])

        return single_depth_array


class SetClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='VALUES', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = 'SET'
        self._print_prefix = 'SET '
        self._quote_format = '"'

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Post-parent-call initialize values.
        self._print_parens = False
        self._always_quote = True
        self._allow_spaces = False

        # Process and save provided clause.
        self.array = clause


class OrderByClauseBuilder(BaseClauseBuilder):
    """"""
    def __init__(self, validation_class, clause, *args, clause_type='ORDER_BY', **kwargs):
        # Pre-parent-call initialize values.
        self._clause_prefix = 'ORDER BY'
        self._print_prefix = 'ORDER BY '
        self._quote_format = '"'

        # Call parent logic.
        super().__init__(validation_class, *args, clause_type=clause_type, **kwargs)

        # Post-parent-call initialize values.
        self._print_parens = False

        # Process and save provided clause.
        self.array = clause

    def __str__(self):
        if len(self.array) > 0:
            # Call parent logic.
            str_value = super().__str__()
            return '\n{0}'.format(str_value)
        else:
            return ''

    def _to_array(self, value):
        # Call parent logic.
        super()._to_array(value)

        if '*' in self._clause_array:
            raise ValueError('The * identifier can only be used in a SELECT clause.')
