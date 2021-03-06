# Copyright (C) 2013-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    common.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# common helper functions

from __future__ import print_function, division
import sys
import subprocess
import time
import os
import imp
import csv

import constants


def abspath_in_dir(d, f):
    try:
        return os.path.abspath(os.path.join(d, f))
    except OSError:
        # getcwd (and thus abspath) can fail on cifs mounts, see https://bugs.python.org/issue17525
        return os.path.normpath(os.path.join(os.environ['PWD'], d, f))

def call(cmd):
    # ensure unix compatibility
    print(cmd)
    if isinstance(cmd, str):
        cmd = filter(lambda a: a != '', cmd.split(' '))
    subprocess.call(cmd)

def import_tool(name, required_env_var, path):
    # Fast path: see if the module has already been imported.
    try:
        return sys.modules[name]
    except KeyError:
        pass

    if required_env_var:
        if required_env_var in os.environ:
            path = os.path.join(os.environ[required_env_var], path)
        else:
            sys.exit('please set the environment variable "%s"' %
                     required_env_var)

    fp, pathname, description = imp.find_module(name, [path])
    try:
        return imp.load_module(name, fp, pathname, description)
    except ImportError:
        sys.exit('required tool %s not found. please check the value of "%s".' %
                 (name, required_env_var))
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close()


def ensure_dir(dir):
    if not os.path.isdir(dir):
        os.mkdir(dir)


def listdir_skip_hidden(dir_path):
    assert os.path.isdir(dir_path), dir_path
    dir_list = [ff for ff in os.listdir(dir_path) if not ff[0] == '.']
    return dir_list


def chunked_sequence_generator(sequence, markerfunc, assertUniqe=False):
    initial_item = next(sequence)
    chunk = [initial_item]
    marker = markerfunc(initial_item)
    known_markers = set()

    for item in sequence:
        if markerfunc(item) == marker:
            chunk.append(item)
        else:
            yield marker, chunk
            known_markers.add(marker)
            chunk = [item]
            marker = markerfunc(item)
            if assertUniqe and marker in known_markers:
                raise Exception('Marker %s appears twice in in sequence %s (using markerfunc=%s).' % (
                    marker, sequence, markerfunc))
    yield marker, chunk


def csv_sequence_generator(csvfile, fields, assertUniqe=False):
    if type(fields) == str:
        fields = [fields]
    gen = chunked_sequence_generator(
        csv.DictReader(open(csvfile)),
        lambda row: tuple([row[f] for f in fields]),
        assertUniqe)
    for item in gen:
        yield item

def build_uid(row, clone_idx=0):
    # build unique id for each trip
    return '%s_%s_%s_%s' % (row[constants.TH.person_id], row[constants.TH.household_id], int(row[constants.TH.depart_minute]), clone_idx)
