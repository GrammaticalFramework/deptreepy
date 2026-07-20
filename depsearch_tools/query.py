import re


def is_search_command(command: str) -> bool:
    search_commands = ['match_trees', 'match_subtrees', 'match_found_in_tree',
                       'match_wordlines', 'find_partial_subtrees', 'find_paths']
    return command in search_commands


def split_by_parentheses(s: str) -> list[str]:
    result = []
    current = ''
    level = 0

    for char in s:
        if char == '(':
            if level == 0:
                if current.strip():
                    result.append(current.strip())
                    current = ''
            level += 1
            if level > 1:
                current += char
        elif char == ')':
            level -= 1
            if level > 0:
                current += char
            elif level == 0:
                cleaned = ' '.join(current.strip().split())
                if cleaned:
                    result.append(cleaned)
                current = ''
        else:
            current += char

    if current.strip():
        result.append(' '.join(current.strip().split()))

    return result


def is_field(word: str) -> bool:
    return word in ["FORM", "LEMMA", "POS", "XPOS", "DEPREL", "FEATS"]


def can_be_flattened(expression):
    """
    Check if a logic expression can be re-expressed without parentheses in its final form
    and without mixing AND and OR operations.

    Args:
        expression (str): The logic expression string

    Returns:
        bool: True if the expression can be flattened, False otherwise
    """
    if not expression or not expression.strip():
        return False

    def parse_expression(s, pos):
        """
        Parse the expression starting at position pos
        Returns (operation_type, sub_expressions, new_pos)
        operation_type: None (for basic pattern), "AND", "OR", or "NOT"
        sub_expressions: list of parsed sub-expressions
        new_pos: new position after parsing
        """
        # Skip whitespace
        while pos < len(s) and s[pos].isspace():
            pos += 1

        if pos >= len(s):
            return None, [], pos

        # Basic pattern: (FIELD value) and (FIELD IN value)
        if s[pos] == '(' and pos + 1 < len(s) and not any(
                s.startswith(op, pos + 1) for op in ["AND", "OR", "NOT"]):
            # Find the matching closing parenthesis
            stack = 1
            start_pos = pos
            pos += 1
            while pos < len(s) and stack > 0:
                if s[pos] == '(':
                    stack += 1
                elif s[pos] == ')':
                    stack -= 1
                pos += 1

            if stack != 0:
                # Unbalanced parentheses
                return None, [], pos
            
            # Handle if this is an IN pattern
            if s.strip()[start_pos + 1 : pos - 1].split()[1] == "IN":
                # This is an IN pattern
                op = "OR"
                sub_expressions = []
                feature = s.strip()[start_pos + 1 : pos - 1].split()[0]
                for value in s[start_pos + 1 : pos - 2].strip().split()[2:]:
                    sub_expressions.append((None, [f"({feature} {value})"]))
                return op, sub_expressions, pos

            # This is a basic pattern
            return None, [s[start_pos:pos]], pos

        # Operation
        nested_flag = False
        if s[pos] == '(':
            pos += 1
            nested_flag = True
        if s[pos:pos + 3] == "AND" or s[pos:pos + 2] == "OR" or s[pos:pos + 3] == "NOT":
            op = s[pos:pos + 3] if s[pos:pos + 3] in ["AND", "NOT"] else "OR"
            pos += len(op)

            # Skip whitespace after operation
            while pos < len(s) and s[pos].isspace():
                pos += 1

            sub_expressions = []

            # Parse all sub-expressions for this operation
            while True:
                # Skip whitespace between sub-expressions
                while pos < len(s) and s[pos].isspace():
                    pos += 1

                if pos >= len(s) or s[pos] != '(':
                    break

                # Store the start position to detect infinite loops
                start_pos = pos

                # Parse the sub-expression

                sub_op, sub_expr, new_pos = parse_expression(s, pos)

                # Check if parsing made progress to prevent infinite loops
                if new_pos <= pos:
                    return None, [], pos  # Error: no progress made

                pos = new_pos
                sub_expressions.append((sub_op, sub_expr))

            if nested_flag:
                pos += 1

            return op, sub_expressions, pos

        # Invalid expression format
        return None, [], pos

    # Check if all operations in the expression tree are of the same type
    def check_operation_consistency(op, sub_expressions):
        if op is None:
            return True, None  # Basic pattern

        # For NOT operation, check its sub-expression
        if op == "NOT":
            if len(sub_expressions) != 1:
                return False, None
            return check_operation_consistency(sub_expressions[0][0],
                                               sub_expressions[0][1])

        # For AND/OR operations
        operation_type = op

        for sub_op, sub_expr in sub_expressions:
            # If sub-expression is a basic pattern
            if sub_op is None:
                continue

            # If sub-expression is NOT
            if sub_op == "NOT":
                consistent, op_type = check_operation_consistency(sub_op,
                                                                  sub_expr)
                if not consistent:
                    return False, None
                if operation_type == op_type:
                    return False, None
                continue

            # If sub-expression is AND/OR
            if sub_op != operation_type:
                return False, None

            # Check sub-expressions recursively
            consistent, _ = check_operation_consistency(sub_op, sub_expr)
            if not consistent:
                return False, None

        return True, operation_type

    # Parse the expression
    expression = expression.strip()
    op, sub_expr, pos = parse_expression(expression, 0)

    # Check if the entire expression was parsed
    if pos != len(expression):
        return False

    # Check operation consistency
    consistent, _ = check_operation_consistency(op, sub_expr)

    return consistent


def parse_word_pattern(pattern: str, negative: bool = False) -> str:
    # Remove outer parentheses if any
    if pattern[0] == '(' and pattern[-1] == ')':
        pattern = pattern[1:-1]

    query_parts = split_by_parentheses(pattern)

    result_query = ""

    if len(query_parts) == 1:
        query_parts = query_parts[0].split()
        if is_field(query_parts[0]):
            if negative:
                comparison_char = "!="
            else:
                comparison_char = "="

            if query_parts[1] == "IN":
                if negative:
                    logic_character = "&"
                else:
                    logic_character = "|"
                for value in query_parts[2:]:
                    expression = query_parts[0] + comparison_char + '"' + value + '"'
                    result_query = result_query + expression + ' ' + logic_character + ' '
                result_query = result_query[:-2]
                return result_query.strip()
            else:
                [field, value] = query_parts
                return field + comparison_char + '"' + value + '"'
        else:
            return ""

    match query_parts[0]:
        case "NOT":
            return parse_word_pattern(query_parts[1], not negative)

        case "AND":
            if not can_be_flattened(pattern):
                return ""

            if negative:
                logic_character = "|"
            else:
                logic_character= "&"

            for sub_query in query_parts[1:]:
                parsed = parse_word_pattern(sub_query, negative).strip()
                if parsed != "":
                    result_query = result_query + parsed
                    result_query = result_query + " " + logic_character + " "
            result_query = result_query[:-2]
            return result_query.strip()

        case "OR":
            if not can_be_flattened(pattern):
                return ""

            if negative:
                logic_character = "&"
            else:
                logic_character = "|"

            for sub_query in query_parts[1:]:
                parsed = parse_word_pattern(sub_query, negative).strip()
                if parsed != "":
                    result_query = result_query + parsed
                    result_query = result_query + " " + logic_character + " "
            result_query = result_query[:-2]
            return result_query.strip()

        case _:
            return ""


def is_empty_query(query: str) -> bool:
    return query.strip() in ['', '[]', '[] []']


def has_only_negative_literals(query: str) -> bool:
    # Check if '!=' exists in the string
    has_not_equal = "!=" in query
    # Check if '=' exists *outside* of '!='
    has_equal = "=" in query.replace("!=", "")
    # Return False only if it contains '!=' but no other '='
    return has_not_equal and not has_equal


def convert_wildcards_to_regex(query: str) -> str:
    def replace_value_wildcards(value: str) -> str:
        # Replace '[...]?' with '.*'
        value = re.sub(r'\[[^\]]+\]\?', '.*', value)
        # Replace remaining '?' with '.*'
        value = value.replace('?', '.*')
        # Replace '*' with '.*'
        value = value.replace('*', '.*')
        return value

    def process_token(token: str) -> str:
        # Replace all field="value" in a token
        def replace_field_value(match):
            field = match.group(1)
            value = match.group(2)
            new_value = replace_value_wildcards(value)
            return f'{field}="{new_value}"'

        return re.sub(r'(\w+)\s*=\s*"([^"]*?)"', replace_field_value, token)

    # Process each [...] block
    return re.sub(r'\[([^\]]+)\]', lambda m: '[' + process_token(m.group(1)) + ']', query)


def remove_suffix_conditions(query: str) -> str:
    """
    # No longer in use, kept for reference.

    Strips out "suffix wildcard" conditions from each [...] bracket token in a corpus 
    query string, then tidies up the boolean operators left behind
    """
    def clean_token(token: str) -> str:
        # Split into parts: field="value", operator (& or |), optional spacing
        parts = re.findall(r'(\w+\s*=\s*"[^"]*"|\&|\||\s+)', token)

        cleaned = []
        last_was_op = False

        for part in parts:
            stripped = part.strip()
            if stripped in {'&', '|'}:
                if not last_was_op and cleaned:
                    cleaned.append(stripped)
                    last_was_op = True
            elif re.match(r'\w+\s*=\s*"\.\*', stripped):  # value starts with .*
                continue
            elif re.match(r'\w+\s*=\s*"[^"]*"', stripped):
                cleaned.append(stripped)
                last_was_op = False
            else:
                continue  # ignore spacing

        # Remove trailing operator if any
        if cleaned and cleaned[-1] in {'&', '|'}:
            cleaned = cleaned[:-1]

        return ' '.join(cleaned)

    # Apply to each [...] token
    return re.sub(r'\[([^\]]+)\]', lambda m: '[' + clean_token(m.group(1)) + ']', query)


def lowercase_fields(query: str) -> str:
    def replacer(match):
        inner = match.group(1)
        # Replace field names before = or != with lowercase versions
        return '[' + re.sub(r'(\w+)(?=\s*(=|!=))', lambda m: m.group(1).lower(), inner) + ']'

    # Match anything inside square brackets
    pattern = r'\[([^\[\]]+)\]'
    return re.sub(pattern, replacer, query)


def postprocessing(parsed_query: str) -> str:
    if is_empty_query(parsed_query):
        return "[]"

    if has_only_negative_literals(parsed_query):
        return "[]"

    parsed_query = convert_wildcards_to_regex(parsed_query)
    # parsed_query = remove_suffix_conditions(parsed_query)
    parsed_query = lowercase_fields(parsed_query)

    return parsed_query


def extract_query(query: str) -> str:
    result_query = ""

    # Extract the pattern part,
    # take only the first part before | if there is any
    query = query.split("|", 1)[0]
    command, pattern = query.strip().split(' ', 1)

    # Skip if the command is not a search command
    if not is_search_command(command):
        return "[]"

    pattern = pattern.strip()
    query_parts = split_by_parentheses(pattern)

    # Handle case when the outer pattern also has parentheses
    if len(query_parts) == 1:
        query_parts = split_by_parentheses(query_parts[0])

    # Handle the special patterns
    match query_parts[0]:
        case "SEQUENCE" | "SUBSEQUENCE" | "SEQUENCE_":
            for token in query_parts[1:]:
                result_query = result_query + "[" + parse_word_pattern(token) + "] "
            result_query = result_query.strip()
        case "TREE" | "TREE_":
            root_pattern = query_parts[1]
            result_query = "[" + parse_word_pattern(root_pattern) + "]"
        case _:
            result_query = "[" + parse_word_pattern(pattern) + "]"

    return postprocessing(result_query)
