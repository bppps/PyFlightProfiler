import re
import shutil
import sys
from contextlib import contextmanager

from flight_profiler.utils.render_util import BOX_HORIZONTAL, COLOR_END, COLOR_FAINT

# Optional platform-specific imports
try:
    import readline
    READLINE_AVAILABLE = readline is not None
except ImportError:
    READLINE_AVAILABLE = False

try:
    import termios
    import tty
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False

try:
    import select as _select_mod
    SELECT_AVAILABLE = True
except ImportError:
    SELECT_AVAILABLE = False


def _is_word_char(c):
    return c.isalnum() or c == '_'


def _find_word_boundary_left(line, pos):
    if pos <= 0:
        return 0
    i = pos
    # skip non-word chars (punctuation + spaces)
    while i > 0 and not _is_word_char(line[i - 1]):
        i -= 1
    # skip word chars
    while i > 0 and _is_word_char(line[i - 1]):
        i -= 1
    return i


def _find_word_boundary_right(line, pos):
    n = len(line)
    if pos >= n:
        return n
    i = pos
    # skip word chars
    while i < n and _is_word_char(line[i]):
        i += 1
    # skip non-word chars (punctuation + spaces)
    while i < n and not _is_word_char(line[i]):
        i += 1
    return i


def _get_cursor_position() -> int:
    """Get current cursor row position in terminal (1-based). Returns -1 if unable to detect."""
    if not TERMIOS_AVAILABLE:
        return -1
    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdout.write('\033[6n')
            sys.stdout.flush()
            response = ''
            while True:
                ch = sys.stdin.read(1)
                response += ch
                if ch == 'R':
                    break
            match = re.search(r'\[(\d+);(\d+)R', response)
            if match:
                return int(match.group(1))
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        pass
    return -1


def _ensure_space_from_bottom(min_lines: int = 3) -> None:
    """Ensure there's enough space from the bottom of terminal."""
    try:
        terminal_height = shutil.get_terminal_size().lines
        cursor_row = _get_cursor_position()
        if cursor_row > 0:
            lines_from_bottom = terminal_height - cursor_row
            if lines_from_bottom < min_lines:
                scroll_lines = min_lines - lines_from_bottom
                print('\n' * scroll_lines, end='')
                sys.stdout.write(f'\033[{scroll_lines}A')
                sys.stdout.flush()
    except Exception:
        pass


class BoxLineEditor:
    """Single-line input editor with box-frame UI and readline-style keybindings."""

    def __init__(self, completions=None):
        self._completions = completions or []
        self._line = ''
        self._cursor_pos = 0
        self._prompt = ''
        self._prompt_len = 2  # ❯ + space
        self._prev_lines = 1  # track display lines for separator adjustment
        self._separator = ''

    # ── Public API ───────────────────────────────────────────────

    def read_input(self, prompt_active: str, prompt_gray: str,
                   show_placeholder: bool = False) -> str:
        """Read a line with box-frame UI. Raises EOFError / KeyboardInterrupt."""
        _ensure_space_from_bottom(5)

        terminal_width = shutil.get_terminal_size().columns
        self._separator = f"{COLOR_FAINT}{BOX_HORIZONTAL * terminal_width}{COLOR_END}"
        placeholder = "help"

        if not TERMIOS_AVAILABLE:
            print(self._separator)
            result = input(prompt_active).strip()
            print(self._separator)
            return result

        # Draw box frame
        print(self._separator)
        sys.stdout.write(prompt_active)
        if show_placeholder:
            sys.stdout.write(f'{COLOR_FAINT}{placeholder}{COLOR_END}')
        sys.stdout.write('\n')
        print(self._separator)

        # Position cursor on input line
        sys.stdout.write('\033[2A')
        sys.stdout.write(f'\033[{self._prompt_len + 1}G')
        sys.stdout.flush()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        # Reset editing state
        self._line = ''
        self._cursor_pos = 0
        self._prompt = prompt_active
        self._prev_lines = 1
        ctrl_d_pressed = False
        ctrl_c_pressed = False
        placeholder_visible = show_placeholder

        # History navigation
        history_index = -1
        saved_line = ''

        try:
            new_settings = termios.tcgetattr(fd)
            new_settings[3] = new_settings[3] & ~termios.ECHO & ~termios.ICANON & ~termios.ISIG
            new_settings[6][termios.VMIN] = 1
            new_settings[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

            # Application cursor keys: real arrows → \033O{A,B,C,D}
            sys.stdout.write('\033[?1h')
            sys.stdout.flush()

            while True:
                ch = sys.stdin.read(1)

                if ch == '\x04':  # Ctrl-D
                    if not self._line.strip():
                        if ctrl_d_pressed:
                            # Move past content lines to separator, then past hint
                            lines_down = self._content_lines() - self._cursor_row() + 1
                            if lines_down > 0:
                                sys.stdout.write(f'\033[{lines_down}B')
                            sys.stdout.write('\n\033[2K')
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            raise EOFError()
                        else:
                            ctrl_d_pressed = True
                            # Move to separator line (content_lines - cursor_row lines down + 1 for separator)
                            sep_offset = self._content_lines() - self._cursor_row() + 1
                            if sep_offset > 0:
                                sys.stdout.write(f'\033[{sep_offset}B')
                            sys.stdout.write('\n')
                            sys.stdout.write(f'{COLOR_FAINT}Press Ctrl-D again to exit{COLOR_END}')
                            # Move back up
                            sys.stdout.write(f'\033[{sep_offset + 1}A')
                            sys.stdout.write(f'\033[{self._cursor_col()}G')
                            sys.stdout.flush()
                    else:
                        self._cleanup_box(prompt_gray)
                        return self._line.strip()

                elif ch == '\x03':  # Ctrl-C
                    if ctrl_c_pressed:
                        sys.stdout.write('\r\033[2K')
                        sep_offset = self._content_lines() - self._cursor_row() + 1
                        if sep_offset > 0:
                            sys.stdout.write(f'\033[{sep_offset}B')
                        sys.stdout.write('\n\033[2K')
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        raise KeyboardInterrupt
                    else:
                        ctrl_c_pressed = True
                        # Move cursor to first input line and clear
                        self._move_to_input_start()
                        sys.stdout.write('\033[2K')
                        sys.stdout.write(self._prompt)
                        old_lines = self._prev_lines
                        self._line = ''
                        self._cursor_pos = 0
                        self._sync_separator(old_lines)
                        if ctrl_d_pressed:
                            ctrl_d_pressed = False
                        # Show hint below separator
                        sep_offset = self._content_lines() - self._cursor_row() + 1
                        if sep_offset > 0:
                            sys.stdout.write(f'\033[{sep_offset}B')
                        sys.stdout.write('\n')
                        sys.stdout.write(f'{COLOR_FAINT}Press Ctrl-C again to exit{COLOR_END}')
                        sys.stdout.write(f'\033[{sep_offset + 1}A')
                        sys.stdout.write(f'\033[{self._prompt_len + 1}G')
                        sys.stdout.flush()

                elif ch == '\n' or ch == '\r':  # Enter
                    if self._line.strip():
                        self._cleanup_box(prompt_gray)
                        return self._line.strip()

                elif ch == '\x7f' or ch == '\x08':  # Backspace
                    if self._cursor_pos > 0:
                        old_lines = self._prev_lines
                        self._line = self._line[:self._cursor_pos - 1] + self._line[self._cursor_pos:]
                        self._cursor_pos -= 1
                        sys.stdout.write('\b')
                        self._redraw_from_cursor()
                        self._sync_separator(old_lines)

                elif ch == '\x01':  # Ctrl+A
                    self._move_cursor_to(0)

                elif ch == '\x05':  # Ctrl+E
                    self._move_cursor_to(len(self._line))

                elif ch == '\x15':  # Ctrl+U
                    if self._cursor_pos > 0:
                        old_lines = self._prev_lines
                        self._delete_range(0, self._cursor_pos)
                        self._sync_separator(old_lines)

                elif ch == '\x0b':  # Ctrl+K
                    if self._cursor_pos < len(self._line):
                        old_lines = self._prev_lines
                        self._line = self._line[:self._cursor_pos]
                        sys.stdout.write('\033[K')
                        # Clear any remaining wrapped lines below cursor
                        new_lines = self._content_lines()
                        if old_lines > new_lines:
                            for _ in range(old_lines - new_lines):
                                sys.stdout.write('\n\033[2K')
                            sys.stdout.write(f'\033[{old_lines - new_lines}A')
                        sys.stdout.flush()
                        self._sync_separator(old_lines)

                elif ch == '\x17':  # Ctrl+W
                    if self._cursor_pos > 0:
                        old_lines = self._prev_lines
                        new_pos = _find_word_boundary_left(self._line, self._cursor_pos)
                        self._delete_range(new_pos, self._cursor_pos)
                        self._sync_separator(old_lines)

                elif ch == '\033':  # Escape sequence
                    seq1 = sys.stdin.read(1)
                    if seq1 == 'O':
                        seq2 = sys.stdin.read(1)
                        if seq2 == 'D':  # Left
                            if self._cursor_pos > 0:
                                self._cursor_pos -= 1
                                sys.stdout.write('\033[D')
                                sys.stdout.flush()
                        elif seq2 == 'C':  # Right
                            if self._cursor_pos < len(self._line):
                                self._cursor_pos += 1
                                sys.stdout.write('\033[C')
                                sys.stdout.flush()
                        elif seq2 == 'A':  # Up - previous history
                            history_len = self._get_history_length()
                            if history_len > 0:
                                if placeholder_visible:
                                    placeholder_visible = False
                                    self._clear_and_rewrite_prompt()
                                if history_index == -1:
                                    saved_line = self._line
                                if history_index < history_len - 1:
                                    history_index += 1
                                    hist_item = self._get_history_item(history_len - history_index)
                                    if hist_item:
                                        self._replace_line(hist_item)
                        elif seq2 == 'B':  # Down - next history
                            if history_index > -1:
                                if placeholder_visible:
                                    placeholder_visible = False
                                    self._clear_and_rewrite_prompt()
                                history_index -= 1
                                if history_index == -1:
                                    self._replace_line(saved_line)
                                else:
                                    history_len = self._get_history_length()
                                    hist_item = self._get_history_item(history_len - history_index)
                                    if hist_item:
                                        self._replace_line(hist_item)
                        elif seq2 == 'H':  # Home
                            self._move_cursor_to(0)
                        elif seq2 == 'F':  # End
                            self._move_cursor_to(len(self._line))
                    elif seq1 == '[':
                        seq2 = sys.stdin.read(1)
                        if seq2 == 'H':
                            self._move_cursor_to(0)
                        elif seq2 == 'F':
                            self._move_cursor_to(len(self._line))
                        elif seq2 == '3':  # Delete key
                            seq3 = sys.stdin.read(1)
                            if seq3 == '~' and self._cursor_pos < len(self._line):
                                old_lines = self._prev_lines
                                self._line = self._line[:self._cursor_pos] + self._line[self._cursor_pos + 1:]
                                self._redraw_from_cursor()
                                self._sync_separator(old_lines)
                        elif seq2 == '1':  # Modifier: \033[1;{mod}{dir}
                            seq3 = sys.stdin.read(1)
                            if seq3 == ';':
                                _mod = sys.stdin.read(1)
                                direction = sys.stdin.read(1)
                                if direction == 'D':
                                    self._move_cursor_to(_find_word_boundary_left(self._line, self._cursor_pos))
                                elif direction == 'C':
                                    self._move_cursor_to(_find_word_boundary_right(self._line, self._cursor_pos))
                        elif seq2 in ('A', 'B', 'C', 'D'):
                            pass  # Mouse wheel / stray CSI arrow — ignore
                    elif seq1 in ('b', 'B'):  # Alt+B
                        self._move_cursor_to(_find_word_boundary_left(self._line, self._cursor_pos))
                    elif seq1 in ('f', 'F'):  # Alt+F
                        self._move_cursor_to(_find_word_boundary_right(self._line, self._cursor_pos))
                    elif seq1 == '\x7f':  # Alt+Backspace
                        if self._cursor_pos > 0:
                            old_lines = self._prev_lines
                            new_pos = _find_word_boundary_left(self._line, self._cursor_pos)
                            self._delete_range(new_pos, self._cursor_pos)
                            self._sync_separator(old_lines)
                    elif seq1 in ('d', 'D'):  # Alt+D
                        if self._cursor_pos < len(self._line):
                            old_lines = self._prev_lines
                            new_pos = _find_word_boundary_right(self._line, self._cursor_pos)
                            self._delete_range(self._cursor_pos, new_pos)
                            self._sync_separator(old_lines)

                elif ch == '\t':  # Tab completion
                    words = self._line.strip().split()
                    if len(words) <= 1 and (len(self._line) == 0 or not self._line.endswith(' ')):
                        prefix = words[0] if words else ''
                        matches = [n for n in self._completions if n.startswith(prefix)]
                        if len(matches) == 1:
                            old_lines = self._prev_lines
                            completion = matches[0] + ' '
                            sys.stdout.write('\b' * self._cursor_pos)
                            sys.stdout.write(' ' * len(self._line))
                            sys.stdout.write('\b' * len(self._line))
                            sys.stdout.write(completion)
                            sys.stdout.flush()
                            self._line = completion
                            self._cursor_pos = len(self._line)
                            self._sync_separator(old_lines)
                        elif len(matches) > 1:
                            # Show below separator
                            sep_offset = self._content_lines() - self._cursor_row() + 1
                            if sep_offset > 0:
                                sys.stdout.write(f'\033[{sep_offset}B')
                            sys.stdout.write('\n')
                            sys.stdout.write(f"{COLOR_FAINT}  {' '.join(matches)}{COLOR_END}")
                            sys.stdout.write(f'\033[{sep_offset + 1}A')
                            sys.stdout.write(f'\033[{self._cursor_col()}G')
                            sys.stdout.flush()

                elif ' ' <= ch <= '~':  # Printable character
                    if placeholder_visible:
                        placeholder_visible = False
                        sys.stdout.write('\033[2K')
                        sys.stdout.write('\r')
                        sys.stdout.write(self._prompt)
                        sys.stdout.flush()
                    if ctrl_d_pressed or ctrl_c_pressed:
                        ctrl_d_pressed = False
                        ctrl_c_pressed = False
                        # Clear hint below separator
                        sep_offset = self._content_lines() - self._cursor_row() + 1
                        if sep_offset > 0:
                            sys.stdout.write(f'\033[{sep_offset}B')
                        sys.stdout.write('\n\033[2K')
                        sys.stdout.write(f'\033[{sep_offset + 1}A')
                        sys.stdout.write(f'\033[{self._cursor_col()}G')
                    old_lines = self._prev_lines
                    self._line = self._line[:self._cursor_pos] + ch + self._line[self._cursor_pos:]
                    self._cursor_pos += 1
                    sys.stdout.write(ch)
                    rest = self._line[self._cursor_pos:]
                    if rest:
                        sys.stdout.write(rest)
                        sys.stdout.write('\b' * len(rest))
                    sys.stdout.flush()
                    self._sync_separator(old_lines)

        finally:
            sys.stdout.write('\033[?1l')
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @contextmanager
    def suppress_input(self):
        """Context manager: suppress echo and drain stray input during command execution."""
        if not TERMIOS_AVAILABLE:
            yield
            return
        fd = None
        old_settings = None
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            new_settings = termios.tcgetattr(fd)
            new_settings[3] = new_settings[3] & ~termios.ECHO & ~termios.ICANON
            new_settings[6][termios.VMIN] = 0
            new_settings[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
        except Exception:
            fd = None
        try:
            yield
        finally:
            if fd is not None and old_settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                if SELECT_AVAILABLE:
                    try:
                        while _select_mod.select([sys.stdin], [], [], 0)[0]:
                            sys.stdin.read(1)
                    except Exception:
                        pass

    # ── Private helpers ──────────────────────────────────────────

    def _content_lines(self):
        """How many terminal rows the prompt + current input occupies."""
        width = shutil.get_terminal_size().columns
        total = self._prompt_len + len(self._line)
        if total == 0:
            return 1
        return (total - 1) // width + 1

    def _cursor_row(self):
        """Which row (1-based, within content area) the cursor is on."""
        width = shutil.get_terminal_size().columns
        col_pos = self._prompt_len + self._cursor_pos
        if col_pos == 0:
            return 1
        return (col_pos - 1) // width + 1

    def _cursor_col(self):
        """Absolute terminal column (1-based) for the cursor."""
        width = shutil.get_terminal_size().columns
        return (self._prompt_len + self._cursor_pos) % width + 1

    def _sync_separator(self, old_lines):
        """Redraw bottom separator if content line count changed."""
        new_lines = self._content_lines()
        self._prev_lines = new_lines
        if new_lines == old_lines:
            return

        # Save cursor position
        cur_row = self._cursor_row()

        if new_lines > old_lines:
            # Separator needs to move down — erase old, draw new
            old_sep_down = old_lines - cur_row + 1
            new_sep_down = new_lines - cur_row + 1
            # Erase old separator
            if old_sep_down > 0:
                sys.stdout.write(f'\033[{old_sep_down}B')
            sys.stdout.write('\r\033[2K')
            # Move to new separator position (further down)
            extra = new_sep_down - old_sep_down
            if extra > 0:
                # Need to create new lines by printing newlines
                for _ in range(extra):
                    sys.stdout.write('\n')
                # We're now at new_sep_down from cursor start
            sys.stdout.write('\r')
            sys.stdout.write(self._separator)
            # Move back to cursor
            if new_sep_down > 0:
                sys.stdout.write(f'\033[{new_sep_down}A')
            sys.stdout.write(f'\033[{self._cursor_col()}G')
        else:
            # Separator needs to move up — erase old, draw new, clear leftover
            old_sep_down = old_lines - cur_row + 1
            new_sep_down = new_lines - cur_row + 1
            # Move to new separator position
            if new_sep_down > 0:
                sys.stdout.write(f'\033[{new_sep_down}B')
            sys.stdout.write('\r')
            sys.stdout.write(self._separator)
            # Clear old separator and any leftover lines below
            extra = old_sep_down - new_sep_down
            for _ in range(extra):
                sys.stdout.write('\n\033[2K')
            # Move back to cursor
            total_down = new_sep_down + extra
            if total_down > 0:
                sys.stdout.write(f'\033[{total_down}A')
            sys.stdout.write(f'\033[{self._cursor_col()}G')

        sys.stdout.flush()

    def _redraw_from_cursor(self):
        """Redraw from cursor to end of content, clearing trailing chars."""
        rest = self._line[self._cursor_pos:]
        sys.stdout.write(rest)
        sys.stdout.write('\033[K')
        if rest:
            sys.stdout.write(f'\033[{len(rest)}D')
        sys.stdout.flush()

    def _move_cursor_to(self, new_pos):
        if new_pos == self._cursor_pos:
            return
        # Use absolute positioning for multi-line safety
        old_row = self._cursor_row()
        self._cursor_pos = new_pos
        new_row = self._cursor_row()
        if new_row < old_row:
            sys.stdout.write(f'\033[{old_row - new_row}A')
        elif new_row > old_row:
            sys.stdout.write(f'\033[{new_row - old_row}B')
        sys.stdout.write(f'\033[{self._cursor_col()}G')
        sys.stdout.flush()

    def _delete_range(self, start, end):
        if start == end:
            return
        old_lines = self._content_lines()
        self._line = self._line[:start] + self._line[end:]
        # Move to start position
        self._move_cursor_to(start)
        # Redraw from cursor
        rest = self._line[self._cursor_pos:]
        sys.stdout.write(rest)
        # Clear everything after the redrawn text
        sys.stdout.write('\033[K')
        new_lines = self._content_lines()
        # If we freed up lines, clear them
        if old_lines > new_lines:
            cur_row = self._cursor_row()
            chars_after = len(rest)
            width = shutil.get_terminal_size().columns
            end_row = (self._prompt_len + start + chars_after - 1) // width + 1 if (self._prompt_len + start + chars_after) > 0 else 1
            lines_below = old_lines - end_row
            for _ in range(lines_below):
                sys.stdout.write('\n\033[2K')
            if lines_below > 0:
                sys.stdout.write(f'\033[{lines_below}A')
        # Move cursor back
        if rest:
            sys.stdout.write(f'\033[{len(rest)}D')
        sys.stdout.flush()

    def _replace_line(self, new_text):
        """Replace entire line content (used by history navigation)."""
        old_lines = self._prev_lines
        # Move to start of input (first row, after prompt)
        self._move_to_input_start()
        # Clear all content lines
        for i in range(old_lines):
            if i > 0:
                sys.stdout.write('\n')
            sys.stdout.write('\033[2K')
        # Move back to first input line
        if old_lines > 1:
            sys.stdout.write(f'\033[{old_lines - 1}A')
        sys.stdout.write('\r')
        sys.stdout.write(self._prompt)
        sys.stdout.write(new_text)
        sys.stdout.flush()
        self._line = new_text
        self._cursor_pos = len(self._line)
        self._sync_separator(old_lines)

    def _move_to_input_start(self):
        """Move cursor to the beginning of the first input line (after prompt)."""
        cur_row = self._cursor_row()
        if cur_row > 1:
            sys.stdout.write(f'\033[{cur_row - 1}A')
        sys.stdout.write('\r')
        sys.stdout.write(f'\033[{self._prompt_len + 1}G')

    def _cleanup_box(self, prompt_gray):
        """Clear the box frame and show the command with gray prompt."""
        lines = self._content_lines()
        # Move to first input line
        cur_row = self._cursor_row()
        if cur_row > 1:
            sys.stdout.write(f'\033[{cur_row - 1}A')
        # Move up to top separator
        sys.stdout.write('\033[1A')
        # Clear top separator and print gray prompt
        sys.stdout.write('\r\033[2K')
        sys.stdout.write(f'{prompt_gray}{self._line}')
        # Move down and clear all remaining lines (old content lines + separator)
        sys.stdout.write('\n\033[J')
        sys.stdout.flush()

    def _clear_and_rewrite_prompt(self):
        sys.stdout.write('\033[2K')
        sys.stdout.write('\r')
        sys.stdout.write(self._prompt)
        sys.stdout.flush()

    @staticmethod
    def _get_history_length():
        if READLINE_AVAILABLE:
            return readline.get_current_history_length()
        return 0

    @staticmethod
    def _get_history_item(index):
        if READLINE_AVAILABLE and index > 0:
            return readline.get_history_item(index)
        return None
