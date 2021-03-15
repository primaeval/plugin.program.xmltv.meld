from xbmcswift2 import Plugin
import html
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib.request, urllib.parse, urllib.error,urllib.parse
import time,datetime,calendar
import threading
import subprocess
import json
import os,os.path
import stat
import platform
import pickle
#import lzma
from html.parser import HTMLParser
from rpc import RPC
from bs4 import BeautifulSoup
import collections
import operator

plugin = Plugin()
big_list_view = False

def decode(x):
    try: return x.decode("utf8")
    except: return x

def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')

def log(v):
    xbmc.log(repr(v),xbmc.LOGERROR)

#log(sys.argv)

def profile():
    return xbmcaddon.Addon().getAddonInfo('profile')

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


def windows():
    if os.name == 'nt':
        return True
    else:
        return False


def android_get_current_appid():
    with open("/proc/%d/cmdline" % os.getpid()) as fp:
        return fp.read().rstrip("\0")


def xmltv_location():
    src = xbmcvfs.translatePath(plugin.get_setting('location'))

    if xbmcvfs.exists(src):
        return src
    else:
        xbmcgui.Dialog().notification("xmltv Meld","xmltv location not found",xbmcgui.NOTIFICATION_ERROR)

def busybox_location():
    busybox_src = xbmcvfs.translatePath(plugin.get_setting('busybox'))

    if xbmc.getCondVisibility('system.platform.android'):
        busybox_dst = '/data/data/%s/busybox' % android_get_current_appid()
        #log((busybox_dst,xbmcvfs.exists(busybox_dst)))
        if not xbmcvfs.exists(busybox_dst) and busybox_src != busybox_dst:
            xbmcvfs.copy(busybox_src, busybox_dst)

        busybox = busybox_dst
    else:
        busybox = busybox_src

    if busybox:
        try:
            st = os.stat(busybox)
            if not (st.st_mode & stat.S_IXUSR):
                try:
                    os.chmod(busybox, st.st_mode | stat.S_IXUSR)
                except:
                    pass
        except:
            pass
    if xbmcvfs.exists(busybox):
        return busybox
    else:
        xbmcgui.Dialog().notification("xmltv Meld","busybox not found",xbmcgui.NOTIFICATION_ERROR)


@plugin.route('/reset')
def reset():
    if xbmc.getCondVisibility('system.platform.android'):
        busybox_dst = '/data/data/%s/busybox' % android_get_current_appid()
        xbmcvfs.delete(busybox_dst)

    if not (xbmcgui.Dialog().yesno("xmltv Meld", "[COLOR red]" + "Remove Channels?" + "[/COLOR]")):
        return

    for storage in ['all_channels', 'channels', 'custom_xmltv', 'folders', 'icons', 'ids', 'm3u_contents', 'names', 'order', 'paths', 'streams', 'subscribe_m3us', 'xml_channels', 'xmltv', 'yo_channels', 'zap_channels', 'zaps']:
        plugin.get_storage(storage).clear()

    xbmcvfs.delete(profile()+'id_order.json')


@plugin.route('/xml_update')
def xml_update():


    #xmltv = plugin.get_storage('xmltv')
    channels = plugin.get_storage('xml_channels')
    for channel in channels:
        data = list(channels[channel])
        #data[0] = data[0].replace('http://rytecepg.dyndns.tv/~rytecepg/epg_data/','http://rytecepg.epgspot.com/epg_data/')
        channels[channel]  = data
    channels.sync()
    xml_urls = {channels[x][0] for x in channels}
    groups = {channels[x][0]:channels[x][1] for x in channels}
    streams = plugin.get_storage('streams')
    m3us = plugin.get_storage('merge_m3us')
    radio = plugin.get_storage('radio')
    ids = plugin.get_storage("ids")
    names = plugin.get_storage("names")

    m3u_streams = {}
    selected_channels = {}
    selected_programmes = []

    htmlparser = HTMLParser()

    '''
    for url in xmltv.keys():
        if "epg.koditvepg.com" in url:
            url2 = url.replace('koditvepg.com','koditvepg2.com')
            xmltv[url2] = xmltv[url]
            del xmltv[url]
    '''

    for url in xml_urls:
        #group = xmltv[url]

        if '\\' in url:
            url = url.replace('\\','/')

        filename = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])

        try:
            with open(filename,'wb') as f:
                if url.startswith('http') or url.startswith('ftp'):
                    data = requests.get(url).content
                    f.write(data)
                else:
                    f.write(xbmcvfs.File(url).read())
        except:
            continue

        if filename.endswith('.xz'):
            f = open(filename+".xml","w")
            subprocess.call([busybox_location(),"xz","-dc",filename],stdout=f,shell=windows())
            f.close()
            data = xbmcvfs.File(filename+'.xml','r').read()
        elif filename.endswith('.gz'):
            try:
                f = open(filename[:-3],"w")
            except:
                f = open(filename,"w")
            subprocess.call([busybox_location(),"gunzip","-dc",filename],stdout=f,shell=windows())
            f.close()
            data = xbmcvfs.File(filename[:-3],'r').read()
        else:
            if filename.startswith("http"):
                #data = xbmcvfs.File(filename,'r').read()
                data = requests.get(filename).content
            else:
                f = open(filename,'r', encoding='utf-8')
                data = f.read()
                f.close()

        encoding = re.search('encoding="(.*?)"',data)
        if encoding:
            encoding = encoding.group(1)

        xchannels = re.findall('(<channel.*?</channel>)', data, flags=(re.I|re.DOTALL))
        xprogrammes = re.findall('(<programme.*?</programme>)', data, flags=(re.I|re.DOTALL))

        for channel in xchannels:
#            if encoding:
#                channel = channel.decode(encoding)
            id = re.search('id="(.*?)"', channel)
            if id:
                id = html.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', channel)
            if name:
                name = html.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', channel)
            if icon:
                icon = icon.group(1)

            #log((id,channels.keys()))
            if id in channels:
                selected_channels[id] = channel
                name = decode(names.get(id,name))
                if radio.get(id):
                    group_label = group+" Radio"
                    radio_flag = 'radio="true" '
                else:
                    group_label = groups.get(url,"dummy")
                    radio_flag = ''
                group_label = decode(group_label)
                m3u_streams[id] = '#EXTINF:-1 %stvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (radio_flag,name,ids.get(id,id),icon,group_label,name,streams.get(id,'http://localhost'))

        for programme in xprogrammes:
#            if encoding:
#                programme = programme.decode(encoding)
            id = re.search('channel="(.*?)"', programme)
            if id:
                id = html.unescape(id.group(1))

                if id in channels:
                    selected_programmes.append(programme)

        if url.endswith('/dummy.xml'):
            for channel in xchannels:
#                if encoding:
#                    channel = channel.decode(encoding)
                id = re.search('id="(.*?)"', channel)
                if id:
                    id = html.unescape(id.group(1))
                if id in channels:
                    now = datetime.datetime.now()
                    now = now.replace(hour=plugin.get_setting('dummy.offset',int),minute=0,second=0)
                    for i in range(0,24*plugin.get_setting('dummy.days',int),plugin.get_setting('dummy.hours',int)):
                        start = now + datetime.timedelta(hours=i)
                        stop = start + datetime.timedelta(hours=plugin.get_setting('dummy.hours',int))
                        title = "%s-%s" % (start.strftime("%Y-%m-%d %H:%M"),stop.strftime("%H:%M"))
                        start = start.strftime("%Y%m%d%H%M%S")
                        stop = stop.strftime("%Y%m%d%H%M%S")
                        offset = divmod(-time.timezone,3600)
                        offset_str = "%02d%02d" % (abs(offset[0]),offset[1])
                        if offset[0] >= 0:
                            offset = "+"+offset_str
                        else:
                            offset = "-"+offset_str
                        programme = '<programme start="%s %s" stop="%s %s" channel="%s"><title lang="en">%s</title></programme>' % (start,offset,stop,offset,id,title)
                        selected_programmes.append(programme)

    return selected_channels, selected_programmes, m3u_streams


    #zap_channels, zap_programmes, zap_m3u_streams = update_zap()
    #yo_channels, yo_programmes, yo_m3u_streams = update_yo()
    #selected_channels.update(zap_channels)
    #selected_channels.update(yo_channels)
    #selected_programmes = selected_programmes + zap_programmes + yo_programmes
    #m3u_streams.update(zap_m3u_streams)
    #m3u_streams.update(yo_m3u_streams)

    '''
    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            channel_order = json.loads(data)
        else:
            channel_order = []
        f.close()
    else:
        channel_order = []
    '''

    channel_order = plugin.get_storage("order")

    xmltv_channels = []
    for id in sorted(channel_order, key=lambda k:channel_order[k]):
        channel_data = selected_channels.get(id)
        if channel_data:
            xmltv_channels.append(channel_data)

    sorted_streams = []
    for id in sorted(channel_order, key=lambda k:channel_order[k]):
        sorted_streams.append(m3u_streams.get(id))


    new_xmltv_channels = []
    for channel in xmltv_channels:
        id = re.search('id="(.*?)"',channel).group(1)
        if id in ids:
            new_id = ids[id]
            channel = re.sub('id=".*?"', 'id="%s"' % new_id, channel)
        if id in names:
            new_name = names[id]
            channel = re.sub('>.*?</display-name', '>%s</display-name' % new_name, channel)
        new_xmltv_channels.append(channel)

    new_selected_programmes = []
    for programme in selected_programmes:
        id = re.search('channel="(.*?)"',programme).group(1)
        if id in ids:
            new_id = ids[id]
            programme = re.sub('channel=".*?"', 'channel="%s"' % new_id, programme)
        new_selected_programmes.append(programme)

    f = xbmcvfs.File(xmltv_location()+"/xmltv.xml",'w')
    f.write('<?xml version="1.0" encoding="utf8"?>\n')
    f.write('<tv generator-info-name="xmltv Meld" >\n\n')
    f.write('\n\n'.join(new_xmltv_channels).encode("utf8"))
    f.write('\n\n\n')
    for programme in new_selected_programmes:
        f.write(programme.encode("utf8")+'\n\n')
    f.write('\n')
    f.write('</tv>\n')
    f.close()

    for url in m3us:
        filename = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])
        success = xbmcvfs.copy(url,filename)
        if success:
            fu = xbmcvfs.File(filename,"r")
            data = fu.read().splitlines()
            #TODO tvg-shift and merge
            for line in data:
                if not line.startswith("#EXTM3U") and line is not None:
                    sorted_streams.append(line)


    f = xbmcvfs.File("special://profile/addon_data/plugin.program.xmltv.meld/channels.m3u8",'w')
    f.write('#EXTM3U\n\n')
    for line in sorted_streams:
        if line is not None:
            line = "%s\n" % line
            f.write(line.encode("utf8"))
    f.write('\n')
    f.close()

    try:
        if xbmcvfs.exists('special://profile/addon_data/plugin.program.xmltv.meld/after_update.py'):
            xbmc.executebuiltin('RunScript(special://profile/addon_data/plugin.program.xmltv.meld/after_update.py)')
    except Exception as e:
        log(e)

    if plugin.get_setting('notification') == 'true':
        xbmcgui.Dialog().notification("xmltv Meld","update finished",sound=False)
    #plugin.set_resolved_url("library://video/addons.xml/")


@plugin.route('/update')
def update():
    if plugin.get_setting('notification') == 'true':
        xbmcgui.Dialog().notification("xmltv Meld","update starting",sound=False)

    xml_channel_xml,xml_programme_xml,xml_m3u_streams = xml_update()
    #log((zap_channels, zap_programmes, zap_m3u_streams))

    channel_xml = xml_channel_xml
    programme_xml = xml_programme_xml
    m3u_streams = xml_m3u_streams

    order = plugin.get_storage('order')

    new_channel_xml = [channel_xml[id] for id in sorted(channel_xml, key=lambda k: order.get(k,-1))]


    f = xbmcvfs.File(xmltv_location()+"/xmltv.xml",'w')
    f.write('<?xml version="1.0" encoding="utf8"?>\n')
    f.write('<tv generator-info-name="xmltv Meld" >\n\n')
    f.write('\n\n'.join(new_channel_xml).encode("utf8"))
    f.write('\n\n\n')
    for programme in programme_xml:
        f.write(programme+'\n\n')
    f.write('\n')
    f.write('</tv>\n')
    f.close()

    f = xbmcvfs.File("special://profile/addon_data/plugin.program.xmltv.meld/channels.m3u8",'w')
    f.write('#EXTM3U\n\n')
    for id in sorted(m3u_streams, key=lambda k: order.get(k,-1)):
        line = m3u_streams[id]
        if line is not None:
            line = "%s\n" % line
            f.write(line)
    f.write('\n')
    f.close()

    if plugin.get_setting('notification') == 'true':
        xbmcgui.Dialog().notification("xmltv Meld","update finished",sound=False)



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
    if url in xmltv:
        del xmltv[url]


@plugin.route('/add_custom_xmltv/<name>/<url>')
def add_custom_xmltv(name,url):
    xmltv = plugin.get_storage('custom_xmltv')
    xmltv[url] = name


@plugin.route('/delete_custom_xmltv/<url>')
def delete_custom_xmltv(url):
    xmltv = plugin.get_storage('custom_xmltv')
    if url in xmltv:
        del xmltv[url]


def create_json_channels():
    path = profile()+'id_order.json'
    if not xbmcvfs.exists(path):
        channels = plugin.get_storage('channels')
        all_channels = dict(list(channels.items()))
        f = xbmcvfs.File(path,'w')
        f.write(json.dumps(sorted(all_channels.keys()),indent=0))
        f.close()


def add_json_channel(id):
    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            channels = json.loads(data)
        else:
            channels = []
        f.close()
    else:
        channels = []
    if id not in channels:
        channels.append(id)
    f = xbmcvfs.File(path,'w')
    f.write(json.dumps(channels,indent=0))


def delete_json_channel(id):
    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            channels = json.loads(data)
        else:
            channels = []
        f.close()
    else:
        channels = []
    if id in channels:
        channels.remove(id)
    f = xbmcvfs.File(path,'w')
    f.write(json.dumps(channels,indent=0))


@plugin.route('/add_dummy_channel/<url>/<label>')
def add_dummy_channel(url,label):
    label = decode(label)

    xmltv = plugin.get_storage('xmltv')
    name = "Dummy Channels"
    xml = "special://home/addons/plugin.program.xmltv.meld/resources/dummy.xml"
    xmltv[xml] = name

    channels = plugin.get_storage('channels')
    for i in range(1,1000):
        id = "dummy%03d" % i
        if id not in channels:
            break

    name =  remove_formatting(label)
    channels[id] = name

    add_json_channel(id)

    streams = plugin.get_storage('streams')
    streams[id] = url

    names = plugin.get_storage('names')
    if id in names:
        del names[id]
    names[id] = name

    #xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_dummy_channel/<url>')
def remove_dummy_channel(url):
    streams = plugin.get_storage('streams')
    channels = plugin.get_storage('channels')
    names = plugin.get_storage('names')
    try:
        index = list(streams.values()).index(url)
    except:
        return
    id = list(streams.keys())[index]
    if id in streams:
        del streams[id]
    if id in channels:
        del channels[id]
    if id in names:
        del names[id]


@plugin.route('/add_channel/<url>/<description>/<name>/<id>/<thumbnail>')
def add_channel(url,description,name,id,thumbnail):
    name = decode(name)
    id = decode(id)
    #log(name)
    channels = plugin.get_storage('xml_channels')
    channels[id] = (url,description,name,id,thumbnail)

    #add_json_channel(id)
    #xbmc.executebuiltin('Container.Refresh')


@plugin.route('/delete_channel/<id>')
def delete_channel(id):
    id = decode(id)

    channels = plugin.get_storage('xml_channels')
    if id in channels:
        del channels[id]


@plugin.route('/rename_channel_id/<id>')
def rename_channel_id(id):
    id = decode(id)

    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    new_id = xbmcgui.Dialog().input(id,new_id)
    if new_id:
        ids[id] = new_id
    elif id in ids:
        del ids[id]


@plugin.route('/rename_channel/<id>/<name>')
def rename_channel(id,name):
    #id = decode(id)

    #all_channels = Yo().all_channels() + xml_all_channels()
    names = plugin.get_storage('names')
    #name = channels[id]
    #country,name,thumbnail = all_channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_all_channels/<url>/<description>')
def add_all_channels(url,description):
    select_channels(url,description,add_all=True)


@plugin.route('/delete_all_channels/<url>/<description>')
def delete_all_channels(url,description):
    select_channels(url,description,remove_all=True)


@plugin.route('/select_channels/<url>/<description>')
def select_channels(url, description, add_all=False, remove_all=False):
#    description = description.decode("utf8")
    #icons = plugin.get_storage('icons')
    #log(url)
    #import web_pdb; web_pdb.set_trace()
    
    if '\\' in url:
        url = url.replace('\\','/')

    filename = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])

    with open(filename,'wb') as f:
        if url.startswith('http') or url.startswith('ftp'):
            data = requests.get(url).content
            f.write(data)
        else:
            f.write(xbmcvfs.File(url).read().encode('utf8'))

    if filename.endswith('.xz'):
        f = open(filename+".xml","w")
        subprocess.call([busybox_location(),"xz","-dc",filename],stdout=f,shell=windows())
        f.close()
        data = xbmcvfs.File(filename+'.xml','r').read()
    elif filename.endswith('.gz'):
        try:
            f = open(filename[:-3],"w")
        except:
            f = open(filename,"w")
        subprocess.call([busybox_location(),"gunzip","-dc",filename],stdout=f,shell=windows())
        f.close()
        data = xbmcvfs.File(filename[:-3],'r').read()
    else:
        data = xbmcvfs.File(filename,'r').read()

    htmlparser = HTMLParser()

    items = []
    channels = plugin.get_storage('xml_channels')

    match = re.findall('<channel(.*?)</channel>', data, flags=(re.I|re.DOTALL))
    if match:

        for m in match:
            id = re.search('id="(.*?)"', m)
            if id:
                id = html.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', m)
            if name:
                name = html.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', m)
            if icon:
                icon = icon.group(1)
            else:
                icon = get_icon_path('tv')

            if add_all == True:
                add_channel(url=url,description=description,name=name, id=id,thumbnail=icon)
            if remove_all == True:
                delete_channel(id.encode("utf8"))

            context_items = []
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add channel", 'RunPlugin(%s)' % (plugin.url_for('add_channel',name=name.encode("utf8"), id=id.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove channel", 'RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

            if id in channels:
                label = "[COLOR yellow]%s[/COLOR]" % name
                path = plugin.url_for(delete_channel, id=id.encode("utf8"))
            else:
                label = name
                path = plugin.url_for('add_channel',url=url,description=description.encode("utf8"),name=name.encode("utf8"), id=id.encode("utf8"),thumbnail=icon)

            #icons[id] = icon

            items.append(
            {
                'label': label,
                'path': path, #plugin.url_for('add_channel',name=name.encode("utf8"), id=id.encode("utf8")),
                'thumbnail':icon,
                'context_menu': context_items,
            })

    return sorted(items, key = lambda x: remove_formatting(x['label']))



def tree(): return collections.defaultdict(tree)


@plugin.route('/add_custom_xmltv_dialog')
def add_custom_xmltv_dialog():
    location = xbmcgui.Dialog().select("xmltv location",["Url","File"])
    if location > -1:
        if location == 0:
            url = xbmcgui.Dialog().input("xmltv Url")
            if url:
                name = xbmcgui.Dialog().input("xmltv Name")
                if name:
                    add_custom_xmltv(name,url)
        else:
            url = xbmcgui.Dialog().browse(1,"xmltv File",'files')
            if url:
                name = xbmcgui.Dialog().input("xmltv Name?")
                if name:
                    add_custom_xmltv(name,url)

@plugin.route('/custom_xmltv')
def custom_xmltv():
    custom = plugin.get_storage('custom_xmltv')

    name = "Dummy Channels"
    url = "special://home/addons/plugin.program.xmltv.meld/resources/dummy.xml"
    if url not in custom:
        custom[url] = name

    items = []
    context_items = []
    items.append(
    {
        'label': "New",
        'path': plugin.url_for('add_custom_xmltv_dialog'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    xmltv = plugin.get_storage('xmltv')
    for url in sorted(custom,key=lambda x: custom[x]):
        name = custom[url]

        context_items = []
        if url not in xmltv:
            context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=name.encode("utf8"), url=url))))
            label = name
        else:
            context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % name
        context_items.append(("[COLOR yellow]Remove xmltv url[/COLOR]", 'RunPlugin(%s)' % (plugin.url_for(delete_custom_xmltv, url=url))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8"),description=name.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8"),description=name.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url,description=name.encode("utf8")),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items

@plugin.route('/rytec_xmltv')
def rytec_xmltv():
    xml_channels = plugin.get_storage("xml_channels")
    xml_urls = {xml_channels[x][0] for x in xml_channels}
    #log(xml_urls)

    #sources = xbmcvfs.File("http://rytecepg.epgspot.com/epg_data/rytec.King.sources.xmls|acceptencoding=","r").read()
    sources = requests.get("http://rytecepg.dyndns.tv/epg_data/rytec.WoS.sources.xml").content.decode('utf8')

    urls = re.findall('<source.*?channels="(.*?)">.*?<description>(.*?)</description>.*?<url>(.*?)<',sources,flags=(re.I|re.DOTALL))

    items = []
    #xmltv = plugin.get_storage('xmltv')
    for channels,description,url in sorted(urls,key=lambda x: x[1]):
        url = url.replace('.gz','.xz')
        context_items = []
        #log(url)
        if url not in xml_urls:
            #context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            #context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'RunPlugin(%s)' % (plugin.url_for('add_all_channels',description=description.encode("utf8"),url=url.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'RunPlugin(%s)' % (plugin.url_for(delete_all_channels,description=description.encode("utf8"), url=url.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url,description=description.encode("utf8")),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items


def xml_all_channels():
    channels = plugin.get_storage('xml_channels')
    all = []
    for id,(url,description,name,id,thumbnail) in list(channels.items()):
        #log((id,(url,description,name,id,thumbnail)))
        all.append({
            "id": decode(id),
            "name": decode(name),
            "thumbnail": thumbnail,
            "provider": "xml",
            "country": description,
        })
    return all

@plugin.route('/channels')
def channels():
    order = plugin.get_storage('order')
    names = plugin.get_storage('names')

    all_channels = xml_all_channels()

    items = []

    for channel in sorted(all_channels, key = lambda k: order.get(k["id"],-1)):
        label = "%d - %s - [%s] - %s" % (order.get(channel["id"],-1),names.get(channel["id"],channel["name"]),channel["provider"],channel["country"])
        id = channel["id"]
        name = channel["name"]
        thumbnail = channel["thumbnail"]
        #log(channel)
        context_items = []
        #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove Channel", 'RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change Channel Id", 'RunPlugin(%s)' % (plugin.url_for(rename_channel_id, id=id.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename Channel", 'RunPlugin(%s)' % (plugin.url_for(rename_channel, id=id.encode("utf8"), name=name.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('move_channel',id=id.encode("utf8")),
            'thumbnail': thumbnail, #icons.get(id, get_icon_path('tv')),
            'context_menu': context_items,
        })

    return items



@plugin.route('/add_dummy_channels/<id>/<path>')
def add_dummy_channels(id,path):
    try: response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except: return
    files = response["files"]
    dirs = {f["file"]:remove_formatting(f["label"]) for f in files if f["filetype"] == "directory"}
    links = {}
    thumbnails = {}
    for f in files:
        if f["filetype"] == "file":
            label = remove_formatting(f["label"])
            url = f["file"]
            links[url] = label
            thumbnails[url] = f["thumbnail"]

    for url in sorted(links):
        label = links[url]
        add_dummy_channel(url=url, label=label)


@plugin.route('/add_merge_m3u')
def add_merge_m3u():
    m3us = plugin.get_storage('merge_m3us')
    add_m3u(m3us)


@plugin.route('/add_subscribe_m3u')
def add_subscribe_m3u():
    m3us = plugin.get_storage('subscribe_m3us')
    add_m3u(m3us)


def add_m3u(m3us):
    type = xbmcgui.Dialog().select("Add m3u",["URL","File"])
    if type == -1:
        return
    if type == 0:
        url = xbmcgui.Dialog().input("Add m3u URL")
        if url:
            name = xbmcgui.Dialog().input("Add m3u URL Name")
            if name:
                m3us[url] = name
    elif type == 1:
        url = xbmcgui.Dialog().browse(1, 'Add m3u File', 'files', mask=".m3u|.m3u8")
        if url:
            name = xbmcgui.Dialog().input("Add m3u File Name")
            if name:
                m3us[url] = name


@plugin.route('/remove_merge_m3u')
def remove_merge_m3u():
    m3us = plugin.get_storage('merge_m3us')
    remove_m3u(m3us)


@plugin.route('/remove_subscribe_m3u')
def remove_subscribe_m3u():
    m3us = plugin.get_storage('subscribe_m3us')
    remove_m3u(m3us)


def remove_m3u(m3us):

    m3u_label = [(x,m3us[x]) for x in sorted(m3us, key=lambda k: m3us[k])]
    labels = [x[1] for x in m3u_label]

    indexes = xbmcgui.Dialog().multiselect("Remove m3us",labels)
    if indexes:
        for index in sorted(indexes, reverse=True):
            url = m3u_label[index][0]
            del m3us[url]


@plugin.route('/remove_xmltv')
def remove_xmltv():
    xmltv = plugin.get_storage('xmltv')

    xmltv_label = [(x,xmltv[x]) for x in sorted(xmltv, key=lambda k: xmltv[k])]
    labels = ["%s - %s" % (x[1],x[0]) for x in xmltv_label]

    indexes = xbmcgui.Dialog().multiselect("Remove xmltv",labels)
    if indexes:
        for index in sorted(indexes, reverse=True):
            url = xmltv_label[index][0]
            del xmltv[url]


@plugin.route('/remove_xmltv_channels')
def remove_xmltv_channels():
    channels = xml_all_channels()

    xmltv_label = [x for x in sorted(channels, key=lambda k: decode(k["name"]))]
    labels = ["%s - %s" % (x["country"],decode(x["name"])) for x in xmltv_label]

    indexes = xbmcgui.Dialog().multiselect("Remove channel",labels)
    if indexes:
        for index in sorted(indexes, reverse=True):
            id = xmltv_label[index]["id"]
            delete_channel(id)

@plugin.route('/delete_busybox')
def delete_busybox():
    busybox = busybox_location()
    success = xbmcvfs.delete(busybox)
    if success:
        xbmcgui.Dialog().notification("xmltv Meld", "busybox deleted")


@plugin.route('/')
def index():
    items = []

    context_items = []
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove xmltv', 'RunPlugin(%s)' % (plugin.url_for('remove_xmltv'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove channels', 'RunPlugin(%s)' % (plugin.url_for('remove_xmltv_channels'))))
    items.append(
    {
        'label': "Custom",
        'path': plugin.url_for('custom_xmltv'),
        'thumbnail':get_icon_path('tv'),
        'context_menu': context_items,
    })
    context_items = []
    items.append(
    {
        'label': "Rytec",
        'path': plugin.url_for('rytec_xmltv'),
        'thumbnail':get_icon_path('tv'),
        'context_menu': context_items,
    })
    '''
    items.append(
    {
        'label': "koditvepg.com GONE PAID",
        'path': plugin.url_for('koditvepg_xmltv'),
        'thumbnail':get_icon_path('tv'),
        'context_menu': context_items,
    })
    '''
    context_items = []
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Merge m3u', 'RunPlugin(%s)' % (plugin.url_for('add_merge_m3u'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove m3u', 'RunPlugin(%s)' % (plugin.url_for('remove_merge_m3u'))))
    items.append(
    {
        'label': 'Channels',
        'path': plugin.url_for('channels'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Update",
        'path': plugin.url_for('start_update'),
        'thumbnail':get_icon_path('settings'),
    })

    context_items = []
    if xbmc.getCondVisibility('system.platform.android'):
        context_items.append(("[COLOR yellow]%s[/COLOR]" %'Delete busybox', 'RunPlugin(%s)' % (plugin.url_for('delete_busybox'))))
    items.append(
    {
        'label': "Reset",
        'path': plugin.url_for('reset'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })
    return items


if __name__ == '__main__':
    create_json_channels()
    try:
        xbmcvfs.mkdirs("special://profile/addon_data/plugin.program.xmltv.meld/temp/")
    except:
        pass
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)
        #plugin.set_view_mode(51)
        #pass
    #plugin.set_content("files")
