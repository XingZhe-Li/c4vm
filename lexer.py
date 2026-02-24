import builtins
from common import Token

def tokenize(src: str) -> list[Token]:
    # tokenize config
    
    # identifier charset
    valid_identifier_charset_start = "abcdefghijklmnopqrstuvwxyz"
    valid_identifier_charset_start += valid_identifier_charset_start.upper()
    valid_identifier_charset_start += '_'

    valid_identifier_charset = valid_identifier_charset_start + "01234567890"

    # tokenize start
    tokens : list[Token] = []

    idx = 0
    line_cnt = 1
    while idx < len(src):
        chr = src[idx]
        if chr == '\n':
            # newline
            tokens.append(
                Token("newline",chr,line_cnt)
            )
            line_cnt += 1
            idx += 1
        elif chr in valid_identifier_charset_start:
            # identifiers
            buf = chr ; idx += 1
            while idx < len(src) and src[idx] in valid_identifier_charset:
                buf += src[idx]
                idx += 1
            tokens.append(
                Token("identifier",buf,line_cnt)
            )
        elif chr == "0":
            buf = "" ; idx += 1
            if idx < len(src) and src[idx] in "01234567":
                # oct mode
                while idx < len(src) and src[idx] in "01234567":
                    buf += src[idx]
                    idx += 1
                tokens.append(
                    Token("integer",int(buf,8),line_cnt)
                )
            elif idx < len(src) and src[idx] == 'x':
                # hex mode
                idx += 1
                while idx < len(src) and src[idx] in "0123456789ABCDEF":
                    buf += src[idx]
                    idx += 1
                tokens.append(Token("integer",int(buf,16),line_cnt))
            elif idx < len(src) and src[idx] == '.': 
                buf = "0." ; idx += 1
                while idx < len(src) and src[idx] in "0123456789":
                    buf += src[idx]
                    idx += 1
                tokens.append(Token("float",float(buf),line_cnt))
            elif idx < len(src) and src[idx] == 'e': 
                buf = "0e" ; idx += 1
                if idx < len(src) and src[idx] == '-':
                    buf += src[idx]
                    idx += 1
                while idx < len(src) and src[idx] in "0123456789":
                    buf += src[idx]
                    idx += 1
                tokens.append(Token("float",float(buf),line_cnt))
            else:
                tokens.append(Token("integer",0,line_cnt))
        elif chr in "123456789":
            # decimal mode
            buf = chr ; idx += 1 ; hasDot = False ; hasE = False
            while idx < len(src) and src[idx] in "0123456789":
                buf += src[idx]
                idx += 1
            if idx < len(src) and src[idx] == '.':
                hasDot = True
                buf += src[idx]
                idx += 1
            elif idx < len(src) and src[idx] == 'e':
                hasE = True
                buf += src[idx]
                idx += 1
            if hasDot:
                while idx < len(src) and src[idx] in "0123456789":
                    buf += src[idx]
                    idx += 1
            elif hasE:
                if idx < len(src) and src[idx] == '-':
                    buf += src[idx]
                    idx += 1
                while idx < len(src) and src[idx] in "0123456789":
                    buf += src[idx]
                    idx += 1
            if hasDot or hasE:
                tokens.append(Token("float",float(buf),line_cnt))
            else:
                tokens.append(Token("integer",int(buf),line_cnt))
        elif chr == "\'":
            buf = "\x00" ; idx += 1
            while idx < len(src) and src[idx] != '\'':
                if src[idx] == '\\':
                    idx += 1
                    if idx < len(src):
                        if src[idx] == 'n':
                            buf = '\n'
                        elif src[idx] == 't':
                            buf = '\t'
                        elif src[idx] == 'x':
                            idx += 1
                            if idx < len(src):
                                high_char = src[idx] 
                                idx += 1
                            if idx < len(src):
                                low_char = src[idx]
                            buf = builtins.chr(int(high_char,16) * 16 + int(low_char,16))
                        else:
                            buf = src[idx]
                        idx += 1
                else:
                    buf = src[idx]
                    idx += 1
            idx += 1 # '
            tokens.append(Token("integer",ord(buf),line_cnt))
        elif chr == "\"":
            buf = "" ; idx += 1
            while idx < len(src) and src[idx] != '\"':
                if src[idx] == '\\':
                    idx += 1
                    if idx < len(src):
                        if src[idx] == 'n':
                            buf += '\n'
                        elif src[idx] == 't':
                            buf += '\t'
                        elif src[idx] == 'x':
                            idx += 1
                            if idx < len(src):
                                high_char = src[idx]
                                idx += 1
                            if idx < len(src):
                                low_char = src[idx]
                            buf += builtins.chr(int(high_char,16) * 16 + int(low_char,16))
                        else:
                            buf += src[idx]
                        idx += 1
                else:
                    buf += src[idx]
                    idx += 1
            idx += 1 # "

            # merge "a" "b" to "ab"
            tidx = len(tokens) - 1
            while tidx >= 0 and tokens[tidx].tktype == "newline":
                tidx -= 1
            if tokens[tidx].tktype == "string":
                tokens[tidx].value += buf
            else:
                tokens.append(Token("string",buf,line_cnt))
        elif chr in "+-*/^&|!<>=~%":
            idx += 1
            if idx < len(src) and src[idx] == "=":
                # >= <= != == &= +=
                tokens.append(Token("operator",chr + "=",line_cnt))
                idx += 1
            elif chr in "&|+-<>" and idx < len(src) and src[idx] == chr:
                # && || ++ -- >> <<
                idx += 1
                if chr in '<>' and idx < len(src) and src[idx] == '=':
                    tokens.append(Token("operator",chr * 2 + '=',line_cnt))
                    idx += 1
                else:
                    tokens.append(Token("operator",chr * 2,line_cnt))
            elif chr == '-' and idx < len(src) and src[idx] == '>':
                idx += 1
                tokens.append(Token("operator",'->',line_cnt))
            elif chr == '/' and idx < len(src):
                if src[idx] == '/':
                    while idx < len(src) and src[idx] != '\n':
                        idx += 1
                elif src[idx] == '*':
                    idx += 1
                    while idx < len(src):
                        while idx < len(src) and src[idx] != '*':
                            if src[idx] == '\n':
                                line_cnt += 1
                            idx += 1
                        idx += 1
                        if idx < len(src) and src[idx] == '/':
                            idx += 1
                            break
                else:
                    tokens.append(Token("operator",chr,line_cnt))
            else:
                tokens.append(Token("operator",chr,line_cnt))
        elif chr in "()[]{},;.":
            # one char operator with no combiner
            idx += 1
            tokens.append(Token("operator",chr,line_cnt))
        elif chr == '#':
            # macros
            if not tokens or tokens[-1].tktype == "newline":
                idx += 1
                buf = ""
                while idx < len(src) and src[idx] != '\n':
                    buf += src[idx]
                    idx += 1
                tokens.append(Token("macro",buf,line_cnt))
            else:
                while idx < len(src) and src[idx] != '\n':
                    idx += 1
            # show throw an exception if its not a newline
        elif chr == '.':
            idx += 1
            if idx < len(src) and src[idx] in "0123456789":
                buf = "."
                while idx < len(src) and src[idx] in "0123456789":
                    buf += src[idx]
                    idx += 1
                tokens.append(Token("float",float(buf),line_cnt))
        else:
            idx += 1

    # remove newline from token stream
    swept_tokens = []
    for tk in tokens:
        if tk.tktype == "newline":
            continue
        swept_tokens.append(tk)
    return swept_tokens