from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib,urlparse
import time,datetime
import threading
import subprocess
import json
import os,os.path
import stat
import platform
import pickle
#import lzma
from HTMLParser import HTMLParser

plugin = Plugin()
big_list_view = False


def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')

def log(v):
    xbmc.log(repr(v),xbmc.LOGERROR)

#log(sys.argv)

def get_icon_path(icon_name):
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_id(),icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(),icon_name)

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

def escape( str ):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str

def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    return str


def delete(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        xbmcvfs.delete(path+file)
    for dir in dirs:
        delete(path + dir + '/')
    xbmcvfs.rmdir(path)


@plugin.route('/reset')
def reset():
    pass


@plugin.route('/update')
def update():
    xmltv = plugin.get_storage('xmltv')

    all_channels = []
    all_programmes = []
    streams = []

    htmlparser = HTMLParser()

    for url in xmltv:

        group = xmltv[url]

        filename = xbmc.translatePath("special://profile/addon_data/plugin.video.xmltv.meld/" + url.rsplit('/',1)[-1])
        xbmcvfs.copy(url,filename)
        if filename.endswith('.xz'):
            f = open(filename+".xml","w")
            subprocess.call(["busybox","xz","-dc",filename],stdout=f,shell=True)
            f.close()
            data = xbmcvfs.File(filename+'.xml','r').read()
        elif filename.endswith('.gz'):
            f = open(filename[:-3],"w")
            subprocess.call(["busybox","gunzip","-dc",filename],stdout=f,shell=True)
            f.close()
            data = xbmcvfs.File(filename[:-3],'r').read()
        else:
            data = xbmcvfs.File(filename,'r').read()

        channels = re.findall('(<channel.*?</channel>)', data, flags=(re.I|re.DOTALL))
        programmes = re.findall('(<programme.*?</programme>)', data, flags=(re.I|re.DOTALL))

        all_channels = all_channels + channels
        all_programmes = all_programmes + programmes

        for channel in channels:
            id = re.search('id="(.*?)"', channel)
            if id:
                id = htmlparser.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', channel)
            if name:
                name = htmlparser.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', channel)
            if icon:
                icon = icon.group(1)

            streams.append('#EXTINF:-1 tvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (name,id,icon,group,name,'http://localhost'))


    f = xbmcvfs.File("special://profile/addon_data/plugin.video.xmltv.meld/xmltv.xml",'w')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<tv generator-info-name="WebGrab+Plus/w MDB &amp; REX Postprocess -- version V2.1.4 -- Jan van Straaten" generator-info-url="http://forums.openpli.org">')
    f.write('\n'.join(all_channels))
    f.write('\n')
    f.write('\n'.join(all_programmes))
    f.write('\n')
    f.write('</tv>\n')
    f.close()

    f = xbmcvfs.File("special://profile/addon_data/plugin.video.xmltv.meld/channels.m3u8",'w')
    f.write('#EXTM3U\n\n')
    f.write('\n'.join(streams).encode("utf8"))
    f.write('\n')
    f.close()




@plugin.route('/start_update')
def start_update():
    t = threading.Thread(target=update)
    t.start()


@plugin.route('/add_xmltv/<name>/<url>')
def add_xmltv(name,url):
    xmltv = plugin.get_storage('xmltv')
    xmltv[url] = name


@plugin.route('/delete_xmltv/<url>')
def delete_xmltv(url):
    xmltv = plugin.get_storage('xmltv')
    del xmltv[url]


@plugin.route('/get_xmltv')
def get_xmltv():
    pass


@plugin.route('/select_channels/<url>')
def select_channels(url):
    filename = xbmc.translatePath("special://profile/addon_data/plugin.video.xmltv.meld/" + url.rsplit('/',1)[-1])
    xbmcvfs.copy(url,filename)

    if filename.endswith('.xz'):
        f = open(filename+".xml","w")
        subprocess.call(["busybox","xz","-dc",filename],stdout=f,shell=True)
        f.close()
        data = xbmcvfs.File(filename+'.xml','r').read()
    elif filename.endswith('.gz'):
        f = open(filename[:-3],"w")
        subprocess.call(["busybox","gunzip","-dc",filename],stdout=f,shell=True)
        f.close()
        data = xbmcvfs.File(filename[:-3],'r').read()
    else:
        data = xbmcvfs.File(filename,'r').read()

    htmlparser = HTMLParser()

    items = []

    match = re.findall('<channel(.*?)</channel>', data, flags=(re.I|re.DOTALL))
    if match:

        for m in sorted(match):
            id = re.search('id="(.*?)"', m)
            if id:
                id = htmlparser.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', m)
            if name:
                name = htmlparser.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', m)
            if icon:
                icon = icon.group(1)

            items.append(
            {
                'label': name,
                'path': plugin.url_for('select_channels',url=url),
                'thumbnail':icon,
            })

    return items


@plugin.route('/rytec_xmltv')
def rytec_xmltv():

    sources = xbmcvfs.File("http://rytecepg.ipservers.eu/epg_data/rytec.King.sources.xml","r").read()
    log(sources)

    urls = re.findall('<source.*?channels="(.*?)">.*?<description>(.*?)</description>.*?<url>(.*?)<',sources,flags=(re.I|re.DOTALL))
    log(urls)

    items = []
    xmltv = plugin.get_storage('xmltv')
    for channels,description,url in sorted(urls,key=lambda x: x[1]):

        context_items = []
        if url not in xmltv:
            context_items.append(("Add xmltv", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            context_items.append(("Remove xmltv", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

    return items


@plugin.route('/koditvepg_xmltv')
def koditvepg_xmltv():

    urls = {'http://epg.koditvepg.com/AT/guide.xml.gz': 'Austria', 'http://epg.koditvepg.com/PL/guide.xml.gz': 'Poland', 'http://epg.koditvepg.com/TR/guide.xml.gz': 'Turkey', 'http://epg.koditvepg.com/IN/guide.xml.gz': 'India', 'http://epg.koditvepg.com/FI/guide.xml.gz': 'Finland', 'http://epg.koditvepg.com/SK/guide.xml.gz': 'Slovakia', 'http://epg.koditvepg.com/CN/guide.xml.gz': 'China', 'http://epg.koditvepg.com/NL/guide.xml.gz': 'Netherlands', 'http://epg.koditvepg.com/GE/guide.xml.gz': 'Georgia', 'http://epg.koditvepg.com/LU/guide.xml.gz': 'Luxembourg', 'http://epg.koditvepg.com/SE/guide.xml.gz': 'Sweden', 'http://epg.koditvepg.com/RU/guide.xml.gz': 'Russia', 'http://epg.koditvepg.com/AU/guide.xml.gz': 'Australia', 'http://epg.koditvepg.com/IS/guide.xml.gz': 'Iceland', 'http://epg.koditvepg.com/AR/guide.xml.gz': 'Argentina', 'http://epg.koditvepg.com/GB/guide.xml.gz': 'United Kingdom', 'http://epg.koditvepg.com/RO/guide.xml.gz': 'Romania', 'http://epg.koditvepg.com/ME/guide.xml.gz': 'Montenegro', 'http://epg.koditvepg.com/NZ/guide.xml.gz': 'New Zealand', 'http://epg.koditvepg.com/DE/guide.xml.gz': 'Germany', 'http://epg.koditvepg.com/DO/guide.xml.gz': 'Dominican Rep.', 'http://epg.koditvepg.com/BR/guide.xml.gz': 'Brazil', 'http://epg.koditvepg.com/TH/guide.xml.gz': 'Thailand', 'http://epg.koditvepg.com/DK/guide.xml.gz': 'Denmark', 'http://epg.koditvepg.com/PH/guide.xml.gz': 'Philippines', 'http://epg.koditvepg.com/AL/guide.xml.gz': 'Albania', 'http://epg.koditvepg.com/PR/guide.xml.gz': 'Puerto Rico', 'http://epg.koditvepg.com/RS/guide.xml.gz': 'Serbia', 'http://epg.koditvepg.com/GR/guide.xml.gz': 'Greece', 'http://epg.koditvepg.com/PA/guide.xml.gz': 'Panama', 'http://epg.koditvepg.com/IE/guide.xml.gz': 'Ireland', 'http://epg.koditvepg.com/TW/guide.xml.gz': 'Taiwan', 'http://epg.koditvepg.com/JP/guide.xml.gz': 'Japan', 'http://epg.koditvepg.com/MX/guide.xml.gz': 'Mexico', 'http://epg.koditvepg.com/FR/guide.xml.gz': 'France', 'http://epg.koditvepg.com/AE/guide.xml.gz': 'United Arab Emirates', 'http://epg.koditvepg.com/MK/guide.xml.gz': 'Macedonia', 'http://epg.koditvepg.com/HU/guide.xml.gz': 'Hungary', 'http://epg.koditvepg.com/IL/guide.xml.gz': 'Israel', 'http://epg.koditvepg.com/SA/guide.xml.gz': 'Saudi Arabia', 'http://epg.koditvepg.com/UA/guide.xml.gz': 'Ukraine', 'http://epg.koditvepg.com/PK/guide.xml.gz': 'Pakistan', 'http://epg.koditvepg.com/LT/guide.xml.gz': 'Lithuania', 'http://epg.koditvepg.com/KZ/guide.xml.gz': 'Kazakhstan', 'http://epg.koditvepg.com/LV/guide.xml.gz': 'Latvia', 'http://epg.koditvepg.com/BE/guide.xml.gz': 'Belgium', 'http://epg.koditvepg.com/PT/guide.xml.gz': 'Portugal', 'http://epg.koditvepg.com/CA/guide.xml.gz': 'Canada', 'http://epg.koditvepg.com/VN/guide.xml.gz': 'Vietnam', 'http://epg.koditvepg.com/HR/guide.xml.gz': 'Croatia', 'http://epg.koditvepg.com/ES/guide.xml.gz': 'Spain', 'http://epg.koditvepg.com/CZ/guide.xml.gz': 'Czech Rep.', 'http://epg.koditvepg.com/EG/guide.xml.gz': 'Egypt', 'http://epg.koditvepg.com/BG/guide.xml.gz': 'Bulgaria', 'http://epg.koditvepg.com/CO/guide.xml.gz': 'Colombia', 'http://epg.koditvepg.com/US/guide.xml.gz': 'United States', 'http://epg.koditvepg.com/NO/guide.xml.gz': 'Norway', 'http://epg.koditvepg.com/BA/guide.xml.gz': 'Bosnia and Herz.', 'http://epg.koditvepg.com/CH/guide.xml.gz': 'Switzerland', 'http://epg.koditvepg.com/IT/guide.xml.gz': 'Italy', 'http://epg.koditvepg.com/SI/guide.xml.gz': 'Slovenia', 'http://epg.koditvepg.com/XK/guide.xml.gz': 'Kosovo'}

    items = []
    xmltv = plugin.get_storage('xmltv')
    for url,description in urls.iteritems():

        context_items = []
        if url not in xmltv:
            context_items.append(("Add xmltv", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            context_items.append(("Remove xmltv", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url),
            'thumbnail':get_icon_path('settings'),
            'context_menu': context_items,
        })

    return sorted(items, key = lambda x: remove_formatting(x["label"]))


@plugin.route('/')
def index():
    items = []

    items.append(
    {
        'label': "Rytec xmltv",
        'path': plugin.url_for('rytec_xmltv'),
        'thumbnail':get_icon_path('settings'),
    })

    items.append(
    {
        'label': "koditvepg.com xmltv",
        'path': plugin.url_for('koditvepg_xmltv'),
        'thumbnail':get_icon_path('settings'),
    })

    items.append(
    {
        'label': "Update",
        'path': plugin.url_for('start_update'),
        'thumbnail':get_icon_path('settings'),
    })
    items.append(
    {
        'label': "Reset",
        'path': plugin.url_for('reset'),
        'thumbnail':get_icon_path('settings'),
    })
    return items


if __name__ == '__main__':

    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)
        #plugin.set_view_mode(51)
        #pass
    #plugin.set_content("files")