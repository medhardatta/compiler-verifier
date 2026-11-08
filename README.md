# Automated C/C++ Compiler Verification Framework

A Python framework that compiles and runs C/C++ test programs across
compilers (GCC, Clang) and optimization levels (-O0 to -O3), validates
outputs, and flags failures and behavioral differences.

## Features
- Compiles every test with every compiler and optimization level
- Output validation against `.expected` files
- Compile-error detection (tests named `ce_*` must fail to compile)
- Runtime timeout handling for hanging programs
- Failure categories: COMPILE_ERROR, TIMEOUT, RUNTIME_ERROR, WRONG_OUTPUT
- Differential testing: flags tests that behave differently across configs
- Baseline comparison to catch regressions
- JSON report in `reports/report.json`

## Requirements
- Python 3.8+
- GCC, G++, Clang, Clang++ available in PATH

## Usage
```
python runner.py --save-baseline   # first run: save known-good results
python runner.py                   # later runs: compare against baseline
```

## Adding a test
Put `name.c` or `name.cpp` in `tests/` with a `name.expected` file
holding the correct output. Name a file `ce_*.c` if it should fail to compile.

## Project layout
```
runner.py
tests/       test programs and expected outputs
build/       compiled binaries (generated)
reports/     JSON report and baseline (generated)
```

## Example finding
`ub_overflow.c` relies on signed integer overflow (undefined behavior).
GCC and Clang produce different output, and the framework flags it.
