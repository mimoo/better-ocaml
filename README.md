The OCaml has real bad error messages. We can do better:

<img width="1269" alt="Screenshot 2023-03-14 at 11 10 14 PM" src="https://user-images.githubusercontent.com/1316043/225153659-c446b85d-5cc3-400c-a6b6-7cb8bfd834f4.png">

## Tell me more

There isn't much I can do about this, unless I start working within the compiler. And these changes are hairy to make.

The next best thing is to parse the compiler output and display it in a better format. Unfortunately:

* this does not allow us to provide more information than the compiler provides (which is often not enough)
* this is a lot of work, as there's no machine-readable format, and there's no convention (linebreaks in different places, different words for the same thing, etc.)

## Installation

you need python3, then install the only dependency:

```console
$ python -m pip install rich
```

## Usage

redirect stderr to the python script

```console
$ dune build ./what/you/want/to/build 2>&1 | python /path/to/ocaml_parser.py
```
