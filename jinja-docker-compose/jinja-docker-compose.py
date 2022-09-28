#!/usr/bin/env python3
import argparse
import yaml
import json
import sys
import re
import subprocess

GPU_DEVICE_PATTERN = re.compile(r'/dev/nvidia\d+')

# support Python 2 or 3
if sys.version_info[0] == 3:
    file_error = FileNotFoundError
else:
    file_error = IOError


def filehandle_if_exists_else_none(fname):
    try:
        return open(fname, 'r')
    except file_error:
        return None


def open_compose_file(fname):
    if not fname:
        return filehandle_if_exists_else_none('jinja-docker-compose.yaml') \
            or filehandle_if_exists_else_none('jinja-docker-compose.yml')
    else:
        return filehandle_if_exists_else_none(fname)

def open_dictionary_file(fname):
    if not fname:
        return filehandle_if_exists_else_none('jinja-docker-compose.dic')
    else:
        return filehandle_if_exists_else_none(fname)


parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', metavar='INPUT_FILE', type=open_compose_file,
                    default='',
                    help='Specify the yaml file to be transformed, default is jinja-docker-compose.yaml'
                         ' and if that does not exist jinja-docker-compose.yml')
parser.add_argument('-D', '--dictionary', metavar='DICTIONARY_FILE', type=open_dictionary_file,
                    default='',
                    help='Specify the dictionary file to use, default is jinja-docker-compose.dic.')
parser.add_argument('-o', '--output', metavar='OUTPUT_FILE', type=argparse.FileType('w'),
                    default='docker-compose.yml',
                    help='Specify an alternate output compose file (default: docker-compose.yml)')
parser.add_argument('-G', '--generate', action='store_true',
                    help='Generate output compose file and exit, do not run docker-compose')
parser.add_argument('-s', '--safeloader', action='store_true',
                    help='Uses the SafeLoader when loading the YAML, this removes the possible exploit that the default FullLoader enables')

(args, extras) = parser.parse_known_args()


#
# Read the dictionary from file
#
with open(args.dictionary.name) as f:
    dic_data = f.read()
dic = json.loads(dic_data)

#
# Rather hacky implementation to obtain the number of GPUs. Look for an improvement in the future
#
try:
    n_gpu = len(subprocess.check_output(['nvidia-smi', '-L'], timeout=10).decode().strip().split('\n'))
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, file_error):
    # Error calling nvidia-smi. setting N_GPU to 0
    n_gpu = 0

print('Adding N_GPU={} to dictionary'.format(n_gpu))
dic['N_GPU']=n_gpu

#
# Use the more secure SafeLoader if requested, see https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
#
if args.safeloader:
    loader = yaml.SafeLoader
else:
    loader = yaml.FullLoader

#
# Transform the input file acording to the dictionary
#
from jinja2 import Template
content = Template(args.file.read()).render(dic)
config = yaml.load(content, Loader=loader)

if config is None:
    raise RuntimeError('Compose file is empty')

yaml.safe_dump(config, args.output, default_flow_style=False)

#
# Do not run docker-compose if disabled
#
if not args.generate:
    from compose.cli.main import main as compose_main
    sys.argv[:] = ['docker-compose', '-f', args.output.name] + extras
    compose_main()