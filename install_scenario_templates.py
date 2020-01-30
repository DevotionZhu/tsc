#!/usr/bin/env python
"""
@file    install_scenario_templates.py
@author  Marek.Heinrich@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2014-12-15
@version $Id: install_scenario_templates.py 8184 2020-01-29 10:26:46Z behr_mi $

Create a scenario template directory mainly by creating a network and copying files.
Relies on a data directory which currently resides in the simo svn trunk/projects/tapas.

# Copyright (C) 2010-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v2.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v20.html
# SPDX-License-Identifier: EPL-2.0
"""
from __future__ import print_function
import os
import sys
import shutil
import subprocess
import optparse
import glob
from xml.sax import parse

import import_navteq
import get_germany_taz
from common import listdir_skip_hidden

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
import edgesInDistricts
import generateBidiDistricts


def getOptions():
    optParser = optparse.OptionParser()
    optParser.add_option("-c", "--clean", action="store_true", default=False,
                         help="remove any old data before processing")
    optParser.add_option("-v", "--verbose", action="store_true",
                         default=False, help="tell me what you are doing")
    optParser.add_option("-p", "--pre", default=os.path.join(os.getcwd(), 'scenario_pre'),
                         help="input dir with pre scenarios")
    optParser.add_option("-t", "--templates", default=os.path.join(os.getcwd(), 'scenario_templates'),
                         help="output dir with scenario templates")
    optParser.add_option("-s", "--scenarios",
                         help="only process selected scenarios")
    optParser.add_option("-i", "--shape-id-column", default="*:NO,RBS_OD_ORT_1412:ORT,Berlin_1223:VBZ_ID",
                         help="name of the column in the shape files which contains the taz id")
    optParser.add_option("--suburb-taz", default="suburb",
                         help="name of taz file for surrounding districts")
    optParser.add_option("--landmarks", default="landmarks",
                         help="name of file listing landmark edges")
    optParser.add_option("--no-network", action="store_true", default=False,
                         help="skip network building")

    (options, args) = optParser.parse_args()

    return options


def evaluate_pre_scen(options):
    for d in sorted(listdir_skip_hidden(options.pre)):
        if os.path.isdir(os.path.join(options.pre, d)):
            if options.scenarios is None or d in options.scenarios.split(","):
                yield d


def create_template_folder(scenario_name, options):
    # create (template) subfolder in scenarios for the 'selected scenarios'
    if options.verbose:
        print("creating template dir for", scenario_name)
    # check if the directory is existing (which means there is old data)
    scenario_pre_dir = os.path.join(options.pre, scenario_name)
    scenario_template_dir = os.path.join(options.templates, scenario_name)
    if os.path.isdir(scenario_template_dir):
        print("Warning! Folder '%s' does exist and may contain old data." %
              scenario_name)
    else:
        # make a new template folder
        os.makedirs(scenario_template_dir)

    # copy static input such as vehicle types, edge lists and processing
    # scripts
    scriptable = False
    for ff in sorted(listdir_skip_hidden(scenario_pre_dir)):
        if ff[-3:] in ['xml', '.py', 'cfg'] and ff[:12] != 'template_gen' and ff != 'setup.py':
            print("copying %s" % ff)
            shutil.copyfile(os.path.join(scenario_pre_dir, ff), os.path.join(scenario_template_dir, ff))
        if ff == "__init__.py":
            scriptable = True

    net_name = 'net.net.xml'
    net_path = os.path.join(scenario_template_dir, net_name)
    if not options.no_network:
        # check for navteq-dlr folder and import from zip
        navteq_dlr_dir = os.path.join(scenario_pre_dir, 'navteq-dlr')
        if os.path.isfile(navteq_dlr_dir):
            # emulate symlink
            navteq_dlr_dir = os.path.join(options.pre, open(navteq_dlr_dir).read().strip())
        if os.path.isdir(navteq_dlr_dir):
            # get the zip file containing the network
            zip_list = [ff for ff in listdir_skip_hidden(
                navteq_dlr_dir) if ff[-4:] == '.zip']
            if len(zip_list) != 1:
                print('could not determine which .zip file to use')
                print(navteq_dlr_dir, ":  ", listdir_skip_hidden(navteq_dlr_dir))
                return scriptable
            navteq_dlr_zip = os.path.join(navteq_dlr_dir, zip_list[0])

            print("starting to import navteq ...")
            # make temporary output folder
            tmp_output_dir = os.path.join(scenario_template_dir, 'tmp_output')
            if os.path.exists(tmp_output_dir):
                shutil.rmtree(tmp_output_dir)
            os.mkdir(tmp_output_dir)
            configs = sorted(glob.glob(os.path.join(options.pre, scenario_name, 'template_gen*.netccfg')))
            importOptions = import_navteq.get_options(
                ['-c', ",".join(configs), '-o', tmp_output_dir, '-v', navteq_dlr_zip])
            import_navteq.importNavteq(importOptions)

            # find netfile
            absPath_net_tmp = []

            def find_net(args, dirname, names):
                if net_name in names:
                    absPath_net_tmp.append(os.path.join(dirname, net_name))

            os.path.walk(tmp_output_dir, find_net, None)
            os.rename(absPath_net_tmp[0], net_path)
            shutil.rmtree(tmp_output_dir)
    setup_file = os.path.join(scenario_pre_dir, 'setup.py')
    if os.path.exists(setup_file):
        subprocess.call(["python", setup_file, scenario_pre_dir, scenario_template_dir])
    if not os.path.exists(net_path):
        print("could not find network data for %s" % scenario_name)

    net = None
    bidi_path = os.path.join(scenario_template_dir, "bidi.taz.xml")
    if not os.path.exists(bidi_path) or os.path.getmtime(bidi_path) < os.path.getmtime(net_path):
        if options.verbose:
            print("calling generateBidiDistricts.main %s, %s" % (net_path, bidi_path))
        net = generateBidiDistricts.main(net_path, bidi_path, 20., 500., True)
    add = bidi_path

    # check for shapes folder and import from shapes
    shapes_dir = os.path.join(scenario_pre_dir, 'shapes')
    if os.path.isfile(shapes_dir):
        # emulate symlink
        shapes_dir = os.path.join(options.pre, open(shapes_dir).read().strip())
    if os.path.isdir(shapes_dir):
        polyconvert = sumolib.checkBinary('polyconvert')
        idCol = dict([e.split(":") for e in options.shape_id_column.split(",")])
        for dbf in glob.glob(os.path.join(shapes_dir, "*.dbf")):
            prefix = os.path.basename(dbf)[:-4]
            tazFile = os.path.join(scenario_template_dir, "districts.taz.xml")
            if prefix in idCol:
                tazFile = os.path.join(scenario_template_dir, prefix + ".taz.xml")
            if options.verbose:
                print("generating taz file %s" % tazFile)
            if not os.path.exists(tazFile) or os.path.getmtime(tazFile) < os.path.getmtime(net_path):
                if options.verbose:
                    print("importing shapes from %s ..." % dbf)
                polyReader = sumolib.shapes.polygon.PolygonReader(True)
                polyFile = os.path.join(scenario_template_dir, prefix + ".poly.xml")
                subprocess.call([polyconvert, "-n", net_path, "-o", polyFile,
                                 "--shapefile-prefixes", os.path.join(
                                     shapes_dir, prefix), "--shapefile.add-param",
                                 "--shapefile.id-column", idCol.get(prefix, idCol["*"])])
                if options.verbose:
                    print("calculating contained edges for %s ..." % polyFile)
                parse(polyFile, polyReader)
                polys = polyReader.getPolygons()
                if net is None:
                    net = sumolib.net.readNet(net_path, withConnections=False, withFoes=False)
                reader = edgesInDistricts.DistrictEdgeComputer(net)
                options.maxspeed = 1000.
                options.minspeed = 0.
                options.complete = False
                options.internal = False
                options.vclass = None
                options.assign_from = True
                options.verbose = False
                options.weighted = False
                options.shapeinfo = False
                options.output = tazFile
                options.merge_separator = None
                options.merge_param = None
                reader.computeWithin(polys, options)
                reader.writeResults(options)
        if options.suburb_taz:
            tazFile = os.path.join(scenario_template_dir, options.suburb_taz + ".taz.xml")
            if options.verbose:
                print("generating taz file %s" % tazFile)
            if not os.path.exists(tazFile) or os.path.getmtime(tazFile) < os.path.getmtime(net_path):
                polys = []
                if net is None:
                    net = sumolib.net.readNet(net_path, withConnections=False, withFoes=False)
                for tazid, shapes in get_germany_taz.get_polys(net=net):
                    for idx, shape in enumerate(shapes):
                        polys.append(sumolib.shapes.polygon.Polygon("%s:%s" % (tazid, idx), shape=shape))
                reader = edgesInDistricts.DistrictEdgeComputer(net)
                options.maxspeed = 1000.
                options.minspeed = 0.
                options.complete = False
                options.internal = False
                options.vclass = None
                options.assign_from = True
                options.verbose = False
                options.weighted = False
                options.shapeinfo = False
                options.output = tazFile
                options.merge_separator = ":"
                reader.computeWithin(polys, options)
                reader.writeResults(options)
            add += "," + tazFile
    lm = os.path.join(scenario_pre_dir, options.landmarks)
    if os.path.isfile(lm):
        if options.verbose:
            print("generating landmark file %s" % lm)
        duarouter = sumolib.checkBinary('duarouter')
        landmarkFile = os.path.join(scenario_template_dir, "landmarks.csv")
        if options.verbose:
            print("generating landmark file %s" % landmarkFile)
        subprocess.call([duarouter, "-n", net_path, "-a", add, "--astar.landmark-distances", lm,
                         "--astar.save-landmark-distances", landmarkFile,
                         "--routing-threads", "24", "-v",
                         "-o", "NUL", "--ignore-errors", "--aggregate-warnings", "5"])
    else:
        print("could not find landmark data for %s" % scenario_name)
    return scriptable

if __name__ == "__main__":
    # generate scenario template folders from
    # input-folders.
    # Each scenario has it's general data sorted
    # in an separate folder underneath pre_scen

    options = getOptions()

    if options.clean and os.path.exists(options.templates):
        print("removing templates %s" % options.templates)
        shutil.rmtree(options.templates)

    script_folders = []
    for folder in evaluate_pre_scen(options):
        print("----- generating template %s" % folder)
        if create_template_folder(folder, options):
            script_folders.append(folder)
    if script_folders:
        with open(os.path.join(options.templates, "scripts.py"), 'w') as scriptpy:
            scriptpy.write("import %s\n" % (",".join(script_folders)))
