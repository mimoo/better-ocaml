import sys
import os
import itertools

from rich.console import Console
from rich.syntax import Syntax
from rich.style import Style
from rich.progress_bar import ProgressBar
from rich.panel import Panel
from rich.console import Group
from rich.console import group
from rich.columns import Columns
from rich.layout import Layout
from rich.text import Text
from rich.table import Table

console = Console()


#
# Functions that can parse errors
#


def parse_error_inner(error, lines):
    # now comes the hard part
    # figure out from the error what it will look like
    desc = error.split(": ")[1]
    if desc.startswith("This expression has type"):
        return parse_expression_mismatch(error, lines)
    elif desc.startswith("The implementation"):
        return parse_interface_match(error, lines)
    else:
        full = error
        for line in lines:
            full += line
        return Text(full)


@group()
def parse_backtrace(lines):
    frame_error = ""
    backtrace = []

    for line in lines:
        # end of suberrors part
        if "Types for method" in line:
            continue

        # start of a suberror
        if "Values do not match:" in line or "The type" in line or "Type\n" in line or "Type " in line:
            # not the first, let's add the previous one
            backtrace.append(frame_error)
            frame_error = line
            continue

        # append to frame error
        frame_error += line

    # add pending one
    backtrace.append(frame_error)

    # reverse the backtrace
    backtrace.reverse()

    # second pass on the backtrace to get split the "impl" and "intf"
    additional_error = ""
    to_delete = []
    for (idx, bt) in enumerate(backtrace):
        if "would escape its scope" in bt:
            to_delete.append(idx)
            additional_error = bt
            continue
        elif "is not compatible with type" in bt:
            backtrace[idx] = bt.split("is not compatible with type")
        elif "is not compatible with the type" in bt:
            backtrace[idx] = bt.split("is not compatible with the type")
        elif "is not included in" in bt:
            backtrace[idx] = bt.split("is not included in")
        elif "but an expression was expected of type" in bt:
            backtrace[idx] = bt.split("but an expression was expected of type")
        else:
            print(bt)
            raise "could not split the suberror in two parts"

        backtrace[idx][0] = backtrace[idx][0].lstrip("Type")
        backtrace[idx][0] = backtrace[idx][0].lstrip("The type")
        backtrace[idx][0] = backtrace[idx][0].lstrip("Values do not match:")
        backtrace[idx][0] = backtrace[idx][0].strip()
        backtrace[idx][1] = backtrace[idx][1].strip()

    # remove the additional error
    to_delete.reverse()
    for idx in to_delete:
        del backtrace[idx]

    # files
    table = Table(expand=True, box=None)
    table.add_column(f"implementation", justify="center",
                     style="cyan", no_wrap=False, ratio=1)
    table.add_column(
        f"expected by interface", style="magenta", justify="center", ratio=1)

    # backtrace
    for (idx, [impl, intf]) in enumerate(backtrace):
        # TODO: we should find the snippet of the previous frame into the next frame and highlight it
        snippet1 = Syntax(impl, "ocaml", line_numbers=True, word_wrap=True)
        snippet2 = Syntax(intf, "ocaml", line_numbers=True, word_wrap=True)

        # from the start and the length of the substring,
        # find the line number and the column to start in the string
        # and the line number and column to end in the string
        def find_ln_and_col(s, start, length):
            # find the line number and colum of the start
            ln = s[:start].count("\n") + 1
            col = start - s[:start].rfind("\n") - 1

            # find the line number and column of the end
            end = start + length
            ln2 = s[:end].count("\n") + 1
            col2 = end - s[:end].rfind("\n") - 1

            return ((ln, col), (ln2, col2))

        if idx != 0:
            [prev_impl, prev_intf] = backtrace[idx-1]

            to_search = prev_impl.split("=")[0].strip()
            pos = impl.find(to_search)
            if pos != -1 and prev_impl.count("=") == 1:
                (start, end) = find_ln_and_col(impl, pos, len(to_search))
                style = Style(bgcolor='deep_pink4')
                snippet1.stylize_range(style, start, end)

            to_search = prev_intf.split("=")[0].strip()
            pos = intf.find(to_search)
            if pos != -1 and prev_intf.count("=") == 1:
                (start, end) = find_ln_and_col(intf, pos, len(to_search))
                style = Style(bgcolor='deep_pink4')
                snippet2.stylize_range(style, start, end)

        col1 = Panel(snippet1)
        col2 = Panel(snippet2)
        table.add_row(col1, col2)

    # add the additional error
    panel = Panel(Text(additional_error),
                  title="Additional error", style="red")
    yield panel

    yield table


@group()
def parse_expression_mismatch(error, lines):
    desc = error
    error_started = False
    the_error = ""

    backtrace = parse_backtrace(lines)

    # description
    yield Text("the implementation does not match the interface\n")

    yield backtrace


@ group()
def parse_interface_match(error, lines):
    # desc part
    desc = error
    in_desc = True

    # bt part
    in_frame = False
    frame_error = ""
    backtrace = []

    # files part
    in_files = False
    expect_actual = []

    for line in lines:
        # end of description
        if in_desc:
            if ":" in line:
                desc += line[:-1]
                in_desc = False
            else:
                desc += line
            continue

        # start of files
        if "File" in line:
            if not in_files:
                backtrace.append(frame_error)
                in_files = True
            (filename, start_line, _) = parse_filename(line)
            expect_actual.append((filename, start_line))

        if in_files:
            continue

        # end of suberrors part
        if "Types for method" in line:
            continue

        # start of a suberror
        if "Values do not match:" in line or "The type" in line or "Type\n" in line or "Type " in line:
            # not the first, let's add the previous one
            if in_frame:
                backtrace.append(frame_error)
            else:
                in_frame = True

            frame_error = line
            continue

        # append to frame error
        frame_error += line

    # reverse the backtrace
    backtrace.reverse()

    # second pass on the backtrace to get split the "impl" and "intf"
    for (idx, bt) in enumerate(backtrace):
        if "is not compatible with type" in bt:
            backtrace[idx] = bt.split("is not compatible with type")
        elif "is not compatible with the type" in bt:
            backtrace[idx] = bt.split("is not compatible with the type")
        elif "is not included in" in bt:
            backtrace[idx] = bt.split("is not included in")
        else:
            raise "could not split the suberror in two parts"

        backtrace[idx][0] = backtrace[idx][0].lstrip("Type")
        backtrace[idx][0] = backtrace[idx][0].lstrip("The type")
        backtrace[idx][0] = backtrace[idx][0].lstrip("Values do not match:")
        backtrace[idx][0] = backtrace[idx][0].strip()
        backtrace[idx][1] = backtrace[idx][1].strip()

    # description
    yield Text("the implementation does not match the interface\n")

    # files
    table = Table(expand=True, box=None)
    table.add_column(f"implementation: {expect_actual[1][0]}\n", justify="center",
                     style="cyan", no_wrap=False, ratio=1)
    table.add_column(
        f"expected by interface: {expect_actual[0][0]}\n", style="magenta", justify="center", ratio=1)

    # backtrace
    for (idx, [impl, intf]) in enumerate(backtrace):
        # TODO: we should find the snippet of the previous frame into the next frame and highlight it
        snippet1 = Syntax(impl, "ocaml", line_numbers=True,
                          start_line=int(expect_actual[1][1]), word_wrap=True)
        snippet2 = Syntax(intf, "ocaml", line_numbers=True,
                          start_line=int(expect_actual[0][1]), word_wrap=True)

        # from the start and the length of the substring,
        # find the line number and the column to start in the string
        # and the line number and column to end in the string
        def find_ln_and_col(s, start, length):
            # find the line number and colum of the start
            ln = s[:start].count("\n") + 1
            col = start - s[:start].rfind("\n") - 1

            # find the line number and column of the end
            end = start + length
            ln2 = s[:end].count("\n") + 1
            col2 = end - s[:end].rfind("\n") - 1

            return ((ln, col), (ln2, col2))

        if idx != 0:
            [prev_impl, prev_intf] = backtrace[idx-1]

            to_search = prev_impl.split("=")[0].strip()
            pos = impl.find(to_search)
            if pos != -1 and prev_impl.count("=") == 1:
                (start, end) = find_ln_and_col(impl, pos, len(to_search))
                style = Style(bgcolor='deep_pink4')
                snippet1.stylize_range(style, start, end)

            to_search = prev_intf.split("=")[0].strip()
            pos = intf.find(to_search)
            if pos != -1 and prev_intf.count("=") == 1:
                (start, end) = find_ln_and_col(intf, pos, len(to_search))
                style = Style(bgcolor='deep_pink4')
                snippet2.stylize_range(style, start, end)

        col1 = Panel(snippet1)
        col2 = Panel(snippet2)
        table.add_row(col1, col2)

    yield table

#
# The rest
#


def parse_filename(line):
    # these are all valid:
    # `File "path", line 104, characters 1-3:`
    # `File "path", lines 104-105, characters 1-3:`
    # `File "path", lines 104-105:`
    line = line.split(",")

    filepath = line[0].lstrip('File "').strip('"')

    start_line = 0
    end_line = 0

    if "lines" in line[1]:
        [start_line, end_line] = line[1][7:].strip().strip(":").split("-")
    else:
        start_line = line[1][6:].strip().strip(":")
        end_line = start_line

    # characters = line[2][12:].split("-")

    # get relative path
    cwd = os.getcwd()
    relpath = os.path.relpath(filepath)

    # format and return
    formatted = f"{relpath}:{start_line}"

    return (formatted, start_line, end_line)


def parse_error(error_lines):
    # parse a single error

    lines = iter(error_lines)

    # first line is the filename
    (filename, start_line, end_line) = parse_filename(next(lines))

    # next might come some snippet or "Error:"
    snippet = []
    marker = ""
    for line in lines:
        # we're out of the snippet
        if line.startswith("Error:"):
            parsed = parse_error_inner(line, lines)
            break

        # line number or `^^^^^^^` (highlight)
        elif line[0].isnumeric():
            parsed = line.split(" | ")
            snippet.append(parsed)
        elif "^" in line:
            marker += line
        else:
            print(line)
            raise "Error: unexpected line in error"

    result = {
        "filename": filename,
        "snippet": snippet,
        "marker": marker,
        "error": parsed,
    }

    return result


def print_error(idx, error):
    # snippet
    snippet = ""
    if len(error["snippet"]) != 0:
        print("\n")

        # start line
        start_line_str = error["snippet"][0][0]
        start_line = int(error["snippet"][0][0])
        last_line = int(error["snippet"][-1][0])

        # snippet as string
        snippet = ""
        for [ln, line] in error["snippet"]:
            snippet += f"{line}"

        # use library to output
        snippet = Syntax(snippet, "ocaml", line_numbers=True,
                         start_line=start_line, highlight_lines=[last_line])

        # highlight characters
        if error["marker"] != "":
            highlight_chars = [pos for pos, char in enumerate(
                error["marker"]) if char == "^"]
            offset = len(start_line_str) + 3
            s1 = highlight_chars[0] - offset
            s2 = highlight_chars[-1] + 1 - offset
            style = Style(bgcolor='deep_pink4')
            snippet.stylize_range(style, (1, s1), (1, s2))

        # print snippet

        # print error description

        # print suberror

    if snippet == "":
        panel_group = Group(
            error["error"],
        )
    else:
        panel_group = Group(
            snippet,
            error["error"],
        )

    # error + filename
    title = f"Error #{idx + 1} in {error['filename']}"
    panel = Panel(panel_group, title=title)
    console.print(panel)


def print_errors(errors):
    for error in errors:
        print_error(error)


def split_errors(compiler_output):
    # split errors from the compiler output
    # (each error starts with `File "`
    in_error = False
    errors = []
    current_error = []

    for line in compiler_output:
        # new error
        if line.startswith('File "') and in_error:
            errors.append(current_error)
            current_error = []

        # bad start
        if not in_error:
            if line[:6] != 'File "':
                raise "Error: expected 'File' at start of line"
            in_error = True

        # just add to the current error
        current_error.append(line)

    # last error pending
    errors.append(current_error)

    # return
    return errors


def main():
    # read stdin
    compiler_output = sys.stdin.readlines()
    if len(compiler_output) == 0:
        print("No errors found!")
        return

    # split errors
    errors = split_errors(compiler_output)
    print(f"Found {len(errors)} errors")

    # print errors
    for (idx, error) in enumerate(errors):
        # error number
        progress = ProgressBar(total=len(errors), completed=idx+1)
        console.print(progress)

        # parse
        res = parse_error(error)
        print_error(idx, res)
        print("\n\n")


if __name__ == "__main__":
    main()
