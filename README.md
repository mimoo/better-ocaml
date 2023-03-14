The OCaml has real bad error messages.

There isn't much I can do about this, unless I start working within the compiler. And these changes are hairy to make.

The next best thing is to parse the compiler output and display it in a better format. Unfortunately:

* this does not allow us to provide more information than the compiler provides (which is often not enough)
* this is a lot of work, as there's no machine-readable format, and there's no convention (linebreaks in different places, different words for the same thing, etc.)

## Installation

```console
$ python -m pip install rich
```

## Usage

```console
$ dune build ./src/lib/pickles/composition_types 2>&1 | python /path/to/ocaml_parser.py
```
