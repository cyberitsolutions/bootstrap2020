#!/usr/bin/python3
# https://sources.debian.org/src/ghostscript/9.56.1~dfsg-1/demos/python/gsapi.py/
# FIXME: license
# FIXME: description

import argparse
import ctypes
import ctypes.util
import pathlib


parser = argparse.ArgumentParser()
parser.add_argument('--DPI', type=int, default=96)
parser.add_argument('input_path', type=pathlib.Path)
args = parser.parse_args()
args.output_path = args.input_path.with_suffix(f'.{args.DPI} DPI.pdf')

out_filename = 'multi_file_output_%d.png'

params = ('gs',
          # These options are taken from /bin/ps2pdfwr
          '-P-',
          '-dSAFER',
          '-q',
          '-P-',
          '-dNOPAUSE',
          '-dBATCH',
          '-sDEVICE=pdfwrite',
          '-sstdout=%stderr',
          f'-sOutputFile={args.output_path}',
          # Everything else is made-up.
          '-dPDFSETTINGS=/screen',  # low-quality settings
          '-dCompatibilityLevel=1.7',  # ...except not PDF 1.5
          f'-dColorImageResolution={args.DPI}',
          f'-dGrayImageResolution={args.DPI}',
          f'-dMonoImageResolution={args.DPI}',)


library_name = ctypes.util.find_library('gs')
assert library_name
libgs = ctypes.CDLL(library_name)
# libgs.gsapi_init_with_args.argtypes = (
#     ctypes.c_void_p,    # instance
#     ctypes.c_int,       # argc
#     ctypes.POINTER(ctypes.POINTER(ctypes.c_char)))  # argv

instance = ctypes.c_void_p()
e = libgs.gsapi_new_instance(ctypes.byref(instance),
                             ctypes.c_void_p(0))
assert e >= 0, 'GSError'
GS_ARG_ENCODING_UTF8 = 1
e = libgs.gsapi_set_arg_encoding(instance, GS_ARG_ENCODING_UTF8)
assert e >= 0, 'GSError'

# Create copy of args in format expected by C.
argc = len(params)
argv = (ctypes.POINTER(ctypes.c_char) * (argc + 1))()
for i, arg in enumerate(params):
    enc_arg = arg.encode('UTF-8')
    argv[i] = ctypes.create_string_buffer(enc_arg)
argv[argc] = None               # NUL-terminated, I guess
e = libgs.gsapi_init_with_args(instance, argc, argv)
assert e >= 0, 'GSError'

pexit_code = ctypes.c_int()
input_path_encoded = str(args.input_path).encode('UTF-8')
e = libgs.gsapi_run_file(instance, input_path_encoded, None, ctypes.byref(pexit_code))
assert e >= 0, 'GSError'
exitcode = pexit_code.value
e = libgs.gsapi_exit(instance)
assert e >= 0, 'GSError'
e = libgs.gsapi_delete_instance(instance)
assert e >= 0, 'GSError'
exit(exitcode)
