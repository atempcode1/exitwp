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


'''
Import

Tested with Wordpress 3.1 and hyde master branch from 2011-03-26
pandoc is required to be installed if conversion from html will be done.

Havent really coded much python (yet) so the design of this code is a bit messy.

EAFP:
   I should do more EAFP to keep the code cleaner, it's even in the python manual glossary.

Flat is better than nested:
   I seem to nest loops a bit uncarefully, should take greater notice about this.

'''
######################################################
# Configration
######################################################
config=yaml.load(file('config.yaml','r'))
wp_exports=config['wp_exports']
build_dir=config['build_dir']
download_images = config['download_images']
target_format=config['target_format']
taxonomy_filter = set(config['taxonomies']['filter'])
taxonomy_entry_filter = config['taxonomies']['entry_filter']
taxonomy_name_mapping = config['taxonomies']['name_mapping']
item_type_filter = set(config['item_type_filter'])
date_fmt=config['date_format']
make_year_month_folder = config['make_year_month_folder']
newurl = config['newurl']

def html2fmt(html, target_format):
    target_format='markdown'
    html = html.replace("\n\n", '<br>')
    # print html.encode("utf-8")
    if target_format=='html':
        return html
    else:
        # This is like very stupid but I was having troubles with unicode encodings and process.POpen
        # f=codecs.open('pandoc.in', 'w', encoding='utf-8')
        # f.write(html)
        # f.close()
        # call(["pandoc","--reference-links","-f","html","-o", "pandoc.out", "-t",target_format, "pandoc.in"])
        # f=codecs.open('pandoc.out', 'r', encoding='utf-8')
        # lines=[]
        # for line in f: lines.append(line)
        # f.close()
        # os.remove('pandoc.in')
        # os.remove('pandoc.out')
        # return ''.join(lines)
        return html2text(html, '')

def parse_wp_xml(file):
    ns = {
        '':'', #this is the default namespace
        'excerpt':"{http://wordpress.org/export/1.1/excerpt/}",
        'content':"{http://purl.org/rss/1.0/modules/content/}",
        'wfw':"{http://wellformedweb.org/CommentAPI/}",
        'dc':"{http://purl.org/dc/elements/1.1/}",
        'wp':"{http://wordpress.org/export/1.1/}"
    }

    tree=ElementTree()

    print "reading: " + wpe

    root=tree.parse(file)
    c=root.find('channel')

    def parse_header():
        return {
            "title": unicode(c.find('title').text),
            "link": unicode(c.find('link').text),
            "description" : unicode(c.find('description').text)
        }

    def parse_items():
        export_items=[]
        xml_items=c.findall('item')
        for i in xml_items:
            taxanomies=i.findall('category')
            export_taxanomies={}
            for tax in taxanomies:
                t_domain=unicode(tax.attrib['domain'])
                t_entry=unicode(tax.text)
                if not (t_domain in taxonomy_filter) and not (t_domain in taxonomy_entry_filter and taxonomy_entry_filter[t_domain]==t_entry):
                    if not t_domain in export_taxanomies:
                            export_taxanomies[t_domain]=[]
                    export_taxanomies[t_domain].append(t_entry)

            def gi(q, unicode_wrap=True):
                namespace=''
                tag=''
                if q.find(':') > 0: namespace, tag=q.split(':',1)
                else: tag=q
                result=i.find(ns[namespace]+tag).text
                if unicode_wrap: result=unicode(result)
                return result

            body=gi('content:encoded')

            img_srcs=[]
            if body is not None:
                try:
                    soup = BeautifulSoup(body)
                    img_tags=soup.findAll('img')
                    for img in img_tags:
                        img_srcs.append(img['src'])
                except:
                    print "could not parse html: " + body
            #print img_srcs

            export_item = {
                'title' : gi('title'),
                'author' : gi('dc:creator'),
                'date' : gi('wp:post_date'),
                'slug' : gi('wp:post_name'),
                'status' : gi('wp:status'),
                'type' : gi('wp:post_type'),
                'wp_id' : gi('wp:post_id'),
                'taxanomies' : export_taxanomies,
                'body' : body,
                'img_srcs': img_srcs,
                'link': gi('link')
                }

            export_items.append(export_item)
        #print export_items
        return export_items

    return {
        'header': parse_header(),
        'items': parse_items(),
    }


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

    def GetNewUrl(item, root=newurl):
        full_dir = root
        dt=datetime.strptime(item['date'],date_fmt)
        y = dt.strftime('%Y')
        full_dir=full_dir+y
        m = dt.strftime('%m')
        full_dir=full_dir+'/'+m+'/'+item['uid']+'.html'
        return full_dir

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

    mapout = open_file(os.path.normpath(build_dir +'/' +  "map.csv"))

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
            print fn    
            out=open_file(fn)
            #yaml_header['layout']='post'
        elif i['type'] == 'page':
            i['uid']=get_item_uid(i, True)
            fn=get_item_path(i)
            print fn    
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

            mapout.write(i['link'])
            mapout.write(', ')
            mapout.write(GetNewUrl(i))
            mapout.write('\n')

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
            out.write(i['body'])
            # out.write(html2fmt(i['body'], target_format))
            out.write('{% endblock %}\n')

            out.close()
    mapout.close()
    print "\n"


wp_exports=glob(wp_exports+'/*.xml')
for wpe in wp_exports:
    data=parse_wp_xml(wpe)
    write_hyde(data, target_format)

print 'done'
