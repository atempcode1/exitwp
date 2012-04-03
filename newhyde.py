#!/usr/bin/env python

from xml.etree.ElementTree import ElementTree
from subprocess import call, PIPE, Popen
import os, codecs
from datetime import datetime
from glob import glob
import re
import sys
import yaml
import tempfile
from BeautifulSoup import BeautifulSoup
from urlparse import urlparse, urljoin
from urllib import urlretrieve
from html2text import html2text
import shutil
import distutils.dir_util


######################################################
# Configration
######################################################
config=yaml.load(file('hydeconfig.yaml','r'))
wp_exports=config['old_hyde_dir']
build_dir=config['build_dir']

def upgrade(origfile, rootpath):

    def open_file(file):
        f=codecs.open(file, 'w', encoding='utf-8')
        return f

    if origfile.lower().endswith('.html') or origfile.lower().endswith('.html~'):
        print "Reading..."
        outfile = open_file(rootpath + "/" + origfile + ".kk")
        inhyde = False
        infile = codecs.open(rootpath + "/" + origfile, "r", "utf-8")
        for linetext in infile:
            # print linetext
            if linetext.startswith("%}") and inhyde:
                outfile.write("---\n")
                inhyde = False
                continue
            if linetext.startswith("{% hyde"):
                outfile.write("---\n")
                inhyde = True
                continue
            if linetext.startswith("{% extends \"_post.html\"") or linetext.startswith("{% block article ") or linetext.startswith("{% endblock"):
                continue  
            outfile.write(linetext.replace("/newblog/media", "/media"))
        outfile.close() 
        infile.close()   
        shutil.move(rootpath + "/" + origfile + ".kk", rootpath + "/" + origfile)


    # search for 
    # {% hyde
    # title: 新的Blog
    # created: 2012-03-14 22:36:00
    # %}
    #replace with
    # ---
    # title: ".htaccess for carisenda.com"
    # created: !!timestamp '2012-02-03 13:14:10'
    # tags:
    #   - htaccess
    #   - fonts
    # tldr: "The Apache .htaccess file used for carisenda.com"
    # subline: "Correct mime-types for woff files, the .htaccess file used on carisenda.com"
    # ---



if (os.path.exists(build_dir)):
    shutil.rmtree(build_dir)
distutils.dir_util.copy_tree(wp_exports, build_dir)

for root, dirs, files in os.walk(build_dir):
    print files
    for eachfile in files:
        upgrade(eachfile, root)

print 'done'
