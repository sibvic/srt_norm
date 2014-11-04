import re
import datetime
import argparse
import functools
import math

class Sub(object):
    REGEX_TIMING = re.compile('(?P<start>\d{2}\:\d{2}\:\d{2,3},\d{3}) \-\-\> (?P<end>\d{2}\:\d{2}\:\d{2,3},\d{3})')
    FORMAT_TIMING = '%H:%M:%S,%f'

    def __init__(self, idx, start, end, text):
        self.idx = idx
        self.start = start
        self.end = end
        self.text = text

    def __str__(self):
        return u"{0}\n{1} --> {2}\n{3}".format(self.idx,
                                               self.start.strftime(self.FORMAT_TIMING)[:12],
                                               self.end.strftime(self.FORMAT_TIMING)[:12],
                                               self.text)

    @classmethod
    def load_from_string(cls, s):
        s_lines = [l.strip() for l in s.strip().split('\n')]
        s_match = cls.REGEX_TIMING.match(s_lines[1])
        s_start = cls._fix_timing_format(s_match.group('start'))
        s_end = cls._fix_timing_format(s_match.group('end'))

        return Sub(
            idx=int(s_lines[0]),
            start=datetime.datetime.strptime(s_start, cls.FORMAT_TIMING),
            end=datetime.datetime.strptime(s_end, cls.FORMAT_TIMING),
            text='\n'.join(s_lines[2:]).strip())

    @staticmethod
    def _fix_timing_format(s):
        s_parts = re.findall(r"[\w']+", s)
        s_fix = ':'.join([part[-2:]for part in s_parts[:-1]])
        s_fix += ',' + s_parts[-1]
        return s_fix


class BaseRule(object):
    def __init__(self, decorated=None):
        self.decorated = decorated

    def execute(self, sub):
        if self.decorated:
            return self.decorated.execute(sub)
        return sub


class WrapRule(BaseRule):
    def __init__(self, limit, decorated=None):
        self.limit = limit
        super(WrapRule, self).__init__(decorated=decorated)

    def execute(self, sub):
        if hasattr(sub, '__iter__'):
            for s in sub:
                s.text = self.wrap(s.text, self.limit)
        else:
            sub.text = self.wrap(sub.text, self.limit)
        return super(WrapRule, self).execute(sub)

    @staticmethod
    def break_to_lines(text):
        lines = text.split('\n')
        if lines is None:
            return [text]
        else:
            return lines
            
    @staticmethod
    def break_to_words(text):
        words = text.split(' ');
        if words is None:
            return [text]
        else:
            return words
        
    @staticmethod    
    def wrap(text, width, target_lines=-1):
        """
        Method try to keep number of lines at minimum by rebalance words equally between 
        the lines to get more or less equal lines length.
        """
        new_text = WrapRule.wrap_real(text, width);
        lines_count = len(WrapRule.break_to_lines(new_text))
        if target_lines == -1 and width > 1:
            return WrapRule.wrap(text, width - 1, lines_count)
        else:
            if target_lines == lines_count and width > 1:
                return WrapRule.wrap(text, width - 1, lines_count)
            else:
                return WrapRule.wrap_real(text, width + 1);

    @staticmethod    
    def wrap_real(text, width):
        """
        A word-wrap function that preserves existing line breaks
        and most spaces in the text. Expects that existing line
        breaks are posix newlines (\n).
        """
        return functools.reduce(lambda line, word, width=width: '%s%s%s' %
                                                      (line,
                                                       ' \n'[(len(line) - line.rfind('\n') - 1
                                                              + len(word.split('\n', 1)[0]
                                                       ) >= width)],
                                                       word),
                      text.split(' '))


class M2LinesRule(BaseRule):
    def __init__(self, decorated=None):
        super(M2LinesRule, self).__init__(decorated=decorated)

    def execute(self, sub):
        subs = []
        if hasattr(sub, '__iter__'):
            for s in sub:
                subs += self._execute_one(s)
        else:
            subs += self._execute_one(sub)
        return super(M2LinesRule, self).execute(subs)

    @staticmethod
    def _execute_one(sub):
        subs = []
        s_lines = sub.text.split('\n')
        if len(s_lines) > 2:
            s_chunks = [s_lines[x:x + 2] for x in range(0, len(s_lines), 2)]
            s_start = sub.start
            s_total_seconds = (sub.end - sub.start).total_seconds()
            s_total_chars_count = len(sub.text)
            s_step = s_total_seconds / len(s_chunks)

            for idx, s_chunk in enumerate(s_chunks):
                s_text = '\n'.join(s_chunk)
                if idx != len(s_chunks) - 1:
                    s_end = s_start + datetime.timedelta(seconds=s_total_seconds * (len(s_text) / s_total_chars_count))
                else:
                    s_end = sub.end
                subs.append(Sub(sub.idx, s_start, s_end, s_text))
                s_start = s_end
        else:
            subs.append(sub)
        return subs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SRT subtitles beautifier.')
    parser.add_argument('--input', type=str)
    parser.add_argument('--output', type=str)
    parser.add_argument('--limit', type=int, default=48)
    parser.add_argument('--encoding', type=str, default="utf-8")

    args = parser.parse_args()
    rules = WrapRule(limit=args.limit, decorated=M2LinesRule())

    subs = []
    with open(args.input, encoding=args.encoding) as f:
        raw_sub = ""
        for line in f.readlines():
            if line.strip('\n'):
                raw_sub += line
            else:
                sub = rules.execute(Sub.load_from_string(raw_sub))
                if hasattr(sub, '__iter__'):
                    subs += sub
                else:
                    subs.append(sub)
                raw_sub = ''

    # Fix subtitle indexes
    for idx, sub in enumerate(subs):
        sub.idx = idx + 1

    with open(args.output, 'wb') as f:
        f.write("\n\n".join([str(s) for s in subs]).encode(args.encoding))
