from ply import lex


letter_regex_doc = r'[a-zA-Z]'
letter_regex_code = r'[a-zA-Z:_]'



class LatexLexer:

    tokens = [
        'COMMENT',
        'CS', # control sequence
        'SCS', # control sequence with one character
        'LBRACE',
        'RBRACE',
        'WHITESPACE',
        'LINEBREAK',
        'TEXARG',
        'ARG',
        'OTHER',
    ]

    t_SCS = r'\\.'
    t_WHITESPACE=r'[ \t]+'
    t_LBRACE=r'\{'
    t_RBRACE=r'\}'
    t_OTHER = r'.'
    t_TEXARG = r'\#+[0-9]'
    t_ARG = r'\#+[a-zA-Z_][a-zA-Z_0-9]+'

    def __init__(self, 
            letter_regex=letter_regex_code):
        self.letter_regex = letter_regex

        self.t_CS = r'\\({})+'.format(self.letter_regex)
        self.lexer = lex.lex(object=self)    

    def t_error(self, t):
         print(f'Illegal character "{t.value[0]}"')
         t.lexer.skip(1)

    def t_COMMENT(self, t):
        r'%.*\n'
        t.lexer.lineno += 1
        return t

    def t_LINEBREAK(self, t):
        r'\n'
        t.lexer.lineno += 1
        return t



    

