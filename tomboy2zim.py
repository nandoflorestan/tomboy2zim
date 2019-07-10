#!/usr/bin/env python3

"""Convert a Tomboy notebook to Zim format, using Python 3.x."""

import sys
import os
import time
from xml.parsers import expat


TOMBOY_DIR = '~/.local/share/tomboy/'
ZIM_DIR = '~/Notebooks/'

NOTEBOOK_NAME = 'Tomboy Notes'
START_NOTE = 'Starts Here'
ENCODING = 'utf-8'


class ZimNote:

    def __init__(self):
        self.name = ''
        self.text = ''
        self.create_date = ''
        self.mtime = None

    def __str__(self):
        s = 'Content-Type: text/x-zim-wiki\n'
        s += 'Wiki-Format: zim 0.4\n'
        s += 'Creation-Date: %s\n' % self.create_date
        s += '\n'
        if self.text[-1] != '\n':
            self.text += '\n'
        s += self.text
        return s


class NoteBuilder:

    def __init__(self, parser):
        self.note = ZimNote()
        self.tag_stack = []
        self.text_stack = []
        self.title_done = False
        self.mtime_done = False

        self.parser = parser
        self.parser.StartElementHandler = self.start_element
        self.parser.EndElementHandler = self.end_element
        self.parser.CharacterDataHandler = self.character_data

    def start_element(self, tag, attr):
        #sys.stdout.write('<%s>' % tag.encode('utf-8'))

        if tag == 'bold':
            self.text_stack.append('**')

        elif tag == 'italic':
            self.text_stack.append('//')

        elif tag == 'strikethrough':
            self.text_stack.append('~~')

        elif tag == 'highlight':
            self.text_stack.append('__')

        elif tag == 'monospace':
            self.text_stack.append("''")

        elif tag.startswith('size:'):
            # It means heading.
            if self.text_stack[-2].endswith('\n') and self.tag_stack[-1] == 'bold':
                if tag == 'size:huge':
                    self.text_stack.pop()   # cancel '**'
                    self.text_stack.append('====== ')
                elif tag == 'size:large':
                    self.text_stack.pop()   # cancel '**'
                    self.text_stack.append('===== ')

        elif tag == 'link:internal':
            self.text_stack.append('[[')

        elif tag == 'list':
            pass

        elif tag == 'list-item':
            self.text_stack.append('\t' * (self.tag_stack.count('list') - 1))
            self.text_stack.append('* ')

        self.tag_stack.append(tag)

    def end_element(self, tag):
        #sys.stdout.write('</%s>' % tag.encode('utf-8'))

        newline_str = ''
        while self.text_stack and self.text_stack[-1] == '\n':
            newline_str += self.text_stack.pop()

        if tag == 'bold':
            if not self.text_stack[-1].startswith(' ====='):
                self.text_stack.append('**')

        elif tag == 'italic':
            self.text_stack.append('//')

        elif tag == 'strikethrough':
            self.text_stack.append('~~')

        elif tag == 'highlight':
            self.text_stack.append('__')

        elif tag == 'monospace':
            self.text_stack.append("''")

        elif tag.startswith('size:'):
            # It means heading.
            if self.tag_stack[-2] == 'bold':
                if tag == 'size:huge':
                    self.text_stack.append(' ======')
                elif tag == 'size:large':
                    self.text_stack.append(' =====')

        elif tag == 'link:internal':
            self.text_stack.append(']]')

        elif tag == 'list':
            pass

        elif tag == 'list-item':
            pass

        if newline_str:
            self.text_stack.append(newline_str)

        endtag = self.tag_stack.pop()
        assert tag == endtag

    def character_data(self, data):
        #sys.stdout.write(data.encode('utf-8'))
        last_tag = self.tag_stack[-1]

        if last_tag == 'title':
            # fix some characters not allowed for path name
            self.note.name = self.fix_link_all(data.strip())

        elif last_tag == 'create-date':
            # remove the time zone info.
            self.note.create_date = data.strip().split('+')[0]

        elif last_tag == 'last-change-date':
            if not self.mtime_done:
                self.note.mtime = int(time.mktime(time.strptime(data.strip().split('.')[0], "%Y-%m-%dT%H:%M:%S")))
                self.mtime_done = True

        elif last_tag == 'link:internal':
            link = data.strip()
            fixed_link = self.fix_link(link)
            self.text_stack.append(fixed_link)
            if link != fixed_link:
                self.text_stack.append('|')
                self.text_stack.append(link)

        elif 'note-content' in self.tag_stack:
            if self.title_done:
                self.text_stack.append(data)
            else:
                # use the first line as the title of this note.
                self.text_stack.append('====== %s ======' % data)
                self.title_done = True

    def get_note(self):
        self.note.text = ''.join(self.text_stack)
        return self.note

    def fix_link(self, s):
        s = s.replace(':', ';')
        s = s.replace('/', '-')
        return s

    def fix_link_all(self, s):
        s = self.fix_link(s)
        s = s.replace(' ', '_')
        return s


def _main(tomboy_dir, zim_dir, can_print=False):
    f = open(os.path.join(zim_dir, 'notebook.zim'), 'w+')
    f.write(NOTEBOOK % (NOTEBOOK_NAME, START_NOTE, zim_dir))
    f.close()

    iterations = 0
    for tnote_id in filter(lambda x: x.endswith('.note'), os.listdir(tomboy_dir)):
        iterations += 1
        parser = expat.ParserCreate()
        builder = NoteBuilder(parser)

        tnote_path = os.path.join(tomboy_dir, tnote_id)
        with open(tnote_path, 'rb') as stream_in:
            parser.ParseFile(stream_in)
            note = builder.get_note()

        znote_path = os.path.join(zim_dir, note.name + '.txt')
        with open(znote_path, 'w', encoding=ENCODING) as stream_out:
            stream_out.write(str(note))

        os.utime(znote_path, (note.mtime, note.mtime))
        # _debug(note)

    if can_print:
        print(f"Success. {iterations} notes converted "
              f"from {tomboy_dir} to {zim_dir}")


def _debug(note):
    print('-' * 80)
    print(note.name)
    print(note)
    input()


def _run_from_shell():
    try:
        tomboy_dir = sys.argv[1]
    except Exception:
        tomboy_dir = os.path.expanduser(TOMBOY_DIR)

    try:
        zim_dir = sys.argv[2]
    except Exception:
        zim_dir = os.path.expanduser(ZIM_DIR)

    if not os.path.exists(zim_dir):
        os.mkdir(zim_dir)
    elif not os.path.isdir(zim_dir):
        sys.stderr.write("The 'zim_dir' is not a directory\n")
        sys.exit(1)

    _main(tomboy_dir, zim_dir, can_print=True)


NOTEBOOK = """[Notebook]
name=%s
home=:%s
icon=None
document_root=%s
slow_fs=False
version=0.4
"""


if __name__ == '__main__':
    _run_from_shell()
