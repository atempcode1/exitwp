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
            if linetext.startswith("{% extends \"_post.html\"") or   linetext.startswith("{% block article ")         or linetext.startswith("{% endblock"):
                continue  
            outfile.write(linetext)
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




def write_hyde(data, target_format):

    sys.stdout.write("writing")
    item_uids={}
    attachments={}

    def get_blog_path(data, path_infix='hyde'):
        name=data['header']['link']
        name=re.sub('^https?','',name)
        name=re.sub('[^A-Za-z0-9_.-]','',name)
        return os.path.normpath(build_dir + '/' + path_infix + '/' +name)

    blog_dir=get_blog_path(data)

    def get_full_dir(dir):
        full_dir=os.path.normpath(blog_dir+'/'+dir)
        if (not os.path.exists(full_dir)):
            os.makedirs(full_dir)
        return full_dir

    def open_file(file):
        f=codecs.open(file, 'w', encoding='utf-8')
        return f

    def get_item_uid(item, date_prefix=False, namespace=''):
        result=None
        # print item
        if namespace not in item_uids:
            item_uids[namespace]={}

        if item['wp_id'] in item_uids[namespace]:
            result=item_uids[namespace][item['wp_id']]
        else:
            uid=[]
            if (date_prefix):
                dt=datetime.strptime(item['date'],date_fmt)
                uid.append(dt.strftime('%Y-%m-%d'))
                uid.append('-')
            s_title=item['slug']
            if s_title is None or s_title == '': s_title=item['title']
            if s_title is None or s_title == '': s_title='untitled'
            s_title=s_title.replace(' ','_')
            s_title=re.sub('[^a-zA-Z0-9_-]','', s_title)
            uid.append(s_title)
            fn=''.join(uid)
            n=1
            while fn in item_uids[namespace]:
                n=n+1
                fn=''.join(uid)+'_'+str(n)
                item_uids[namespace][i['wp_id']]=fn
            result=fn
        # print item_uids
        return result

    def get_item_path(item, dir=''):
        full_dir=get_full_dir(dir)
        if make_year_month_folder and not dir=='':
            dt=datetime.strptime(item['date'],date_fmt)
            y = dt.strftime('%Y')
            full_dir=os.path.normpath(full_dir+'/'+y)
            if (not os.path.exists(full_dir)):
                os.makedirs(full_dir)
            m = dt.strftime('%m')
            full_dir=os.path.normpath(full_dir+'/'+m)
            if (not os.path.exists(full_dir)):
                os.makedirs(full_dir)
        filename_parts=[full_dir,'/']
        filename_parts.append(item['uid'])
        filename_parts.append('.')
        #filename_parts.append(target_format)
        filename_parts.append('html')
        return ''.join(filename_parts)

    def get_attachment_path(src, dir, dir_prefix='a'):
        try:
            files=attachments[dir]
        except KeyError:
            attachments[dir]=files={}

        try:
            filename=files[src]
        except KeyError:
            file_root, file_ext=os.path.splitext(os.path.basename(urlparse(src)[2]))
            file_infix=1
            if file_root=='': file_root='1'
            current_files=files.values()
            maybe_filename=file_root+file_ext
            while maybe_filename in current_files:
                maybe_filename=file_root+'-'+str(file_infix)+file_ext
                file_infix=file_infix+1
            files[src]=filename=maybe_filename

        target_dir=os.path.normpath(blog_dir+'/'+dir_prefix +'/' + dir)
        target_file=os.path.normpath(target_dir+'/'+filename)

        if (not os.path.exists(target_dir)):
            os.makedirs(target_dir)

        #if src not in attachments[dir]:
        ##print target_name
        return target_file

    #data['items']=[]

    for i in data['items']:
        sys.stdout.write(".")
        sys.stdout.flush()
        out=None
        yaml_header = {
          'title' : i['title'],
          #'author' : i['author'],
          #'slug' : i['slug'],
          #'status' : i['status'],
          #'wordpress_id' : i['wp_id'],
        }

        if i['type'] == 'post':
            i['uid']=get_item_uid(i, True)
            fn=get_item_path(i, dir='_posts')
            out=open_file(fn)
            #yaml_header['layout']='post'
        elif i['type'] == 'page':
            i['uid']=get_item_uid(i, True)
            fn=get_item_path(i)
            out=open_file(fn)
            #yaml_header['layout']='page'
        elif i['type'] in item_type_filter:
            pass
        else:
            print "Unknown item type :: " +  i['type']


        if download_images:
            for img in i['img_srcs']:
                urlretrieve(urljoin(data['header']['link'],img.decode('utf-8')), get_attachment_path(img, i['uid']))


        if out is not None:
            def toyaml(data):
                return yaml.safe_dump(data, default_flow_style=False).decode('utf-8')

            tax_out={}
            for taxonomy in i['taxanomies']:
                for tvalue in i['taxanomies'][taxonomy]:
                    t_name=taxonomy_name_mapping.get(taxonomy,taxonomy)
                    if t_name is 'tags':
                        if t_name not in tax_out: tax_out[t_name]=[]
                        tax_out[t_name].append(tvalue)

            out.write('{% extends "_post.html" %}\n')
            out.write('{% hyde\n')
            if len(yaml_header)>0: out.write(toyaml(yaml_header))
            out.write('created: ' + i['date'] + '\n');
            if len(tax_out)>0: out.write(toyaml(tax_out))
            out.write('%}\n\n')

            out.write('{% block article %}\n')
            out.write(html2fmt(i['body'], target_format))
            out.write('{% endblock %}\n')

            out.close()
    print "\n"


if (os.path.exists(build_dir)):
    shutil.rmtree(build_dir)
distutils.dir_util.copy_tree(wp_exports, build_dir)

for root, dirs, files in os.walk(build_dir):
    print files
    for eachfile in files:
        upgrade(eachfile, root)

print 'done'
