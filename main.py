from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import random
import urllib,urlparse
import time,datetime,calendar
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


def busybox_location():
    busybox_src = xbmc.translatePath(plugin.get_setting('busybox'))

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
    xmltv = plugin.get_storage('xmltv')
    xmltv.clear()
    channels = plugin.get_storage('channels')
    channels.clear()
    zaps = plugin.get_storage('zaps')
    zaps.clear()
    zap_channels = plugin.get_storage('zap_channels')
    zap_channels.clear()

    xbmcvfs.delete(profile()+'id_order.json')


@plugin.route('/update_zap')
def update_zap():
    zaps = plugin.get_storage('zaps')

    zap_channels = plugin.get_storage('zap_channels')

    streams = []
    selected_channels = {}
    selected_programmes = []

    gridtimeStart = (int(time.mktime(time.strptime(str(datetime.datetime.now().replace(microsecond=0,second=0,minute=0)), '%Y-%m-%d %H:%M:%S'))))

    for url,name in zaps.iteritems():

        count = 0

        gridtime = gridtimeStart
        while count < (8 * int(plugin.get_setting('zap.days') or "1")):
            u = url + '&time=' + str(gridtime)
            data = xbmcvfs.File(u,'r').read()
            j = json.loads(data)
            channels = j.get('channels')

            for channel in channels:
                callSign = channel.get('callSign')
                id = channel.get('id') #channelId?

                if id not in zap_channels:
                    continue

                thumbnail = "http:" + channel.get('thumbnail').replace('?w=55','')

                xchannel = '<channel id="' + id + '">\n'
                xchannel += '\t<display-name>' + escape(callSign) + '</display-name>\n'
                if thumbnail:
                    xchannel += '\t<icon src="' + thumbnail + '"/>\n'
                xchannel += '</channel>'

                if id in zap_channels:
                    selected_channels[id] = xchannel
                    streams.append('#EXTINF:-1 tvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (callSign,id,thumbnail,name,callSign,'http://localhost'))

                events = channel.get('events')
                for event in events:

                    startTime = time.strptime(event.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')
                    endTime = time.strptime(event.get('endTime'), '%Y-%m-%dT%H:%M:%SZ')
                    startTime = time.strftime("%Y%m%d%H%M%S +0000",startTime)
                    endTime = time.strftime("%Y%m%d%H%M%S +0000",endTime)

                    program = event.get('program')
                    title = program.get('title')
                    episodeTitle = program.get('episodeTitle')
                    shortDesc = program.get('shortDesc')
                    releaseYear = program.get('releaseYear')
                    season = program.get('season')
                    episode = program.get('episode')

                    programme = '<programme start=\"' + startTime + '\" stop=\"' + endTime + '\" channel=\"' + id  + '\">\n'
                    if title:
                        programme += '\t<title>' + escape(title) + '</title>\n'
                    if episodeTitle:
                        programme += '\t<sub-title>' + escape(episodeTitle) + '</sub-title>\n'
                    if shortDesc:
                        programme += '\t<desc>' + escape(shortDesc) + '</desc>\n'
                    if season and episode:
                        programme += "\t<episode-num system=\"xmltv_ns\">" + season +  "." + episode + ".</episode-num>\n"
                    if releaseYear:
                        programme += '\t<date>' + releaseYear + '</date>\n'
                    programme += "</programme>"

                    if id in zap_channels:
                        selected_programmes.append(programme)

            count += 1
            gridtime = gridtime + 10800

    return selected_channels,selected_programmes


@plugin.route('/update')
def update():
    xbmcgui.Dialog().notification("xmltv Meld","update starting",sound=False)

    xmltv = plugin.get_storage('xmltv')
    channels = plugin.get_storage('channels')
    ids = plugin.get_storage("ids")
    names = plugin.get_storage("names")

    streams = []
    selected_channels = {}
    selected_programmes = []

    htmlparser = HTMLParser()

    for url in xmltv:

        group = xmltv[url]

        if '\\' in url:
            url = url.replace('\\','/')
        filename = xbmc.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])
        xbmcvfs.copy(url,filename)

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
        data = data.decode("utf8")

        xchannels = re.findall('(<channel.*?</channel>)', data, flags=(re.I|re.DOTALL))
        xprogrammes = re.findall('(<programme.*?</programme>)', data, flags=(re.I|re.DOTALL))

        for channel in xchannels:
            id = re.search('id="(.*?)"', channel)
            if id:
                id = htmlparser.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', channel)
            if name:
                name = htmlparser.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', channel)
            if icon:
                icon = icon.group(1)

            if id in channels:
                selected_channels[id] = channel
                name = names.get(id,name)
                streams.append('#EXTINF:-1 tvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (name,ids.get(id,id),icon,group,name,'http://localhost'))

        for programme in xprogrammes:
            id = re.search('channel="(.*?)"', programme)
            if id:
                id = htmlparser.unescape(id.group(1))

                if id in channels:
                    selected_programmes.append(programme)

    zap_channels, zap_programmes = update_zap()
    selected_channels.update(zap_channels)
    selected_programmes = selected_programmes + zap_programmes

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
    xmltv_channels = []
    for id in channel_order:
        channel_data = selected_channels.get(id)
        if channel_data:
            xmltv_channels.append(channel_data)


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

    f = xbmcvfs.File("special://profile/addon_data/plugin.program.xmltv.meld/xmltv.xml",'w')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<tv generator-info-name="xmltv Meld" >\n\n')
    f.write('\n\n'.join(new_xmltv_channels).encode("utf8"))
    f.write('\n\n\n')
    f.write('\n\n'.join(new_selected_programmes).encode("utf8"))
    f.write('\n')
    f.write('</tv>\n')
    f.close()

    f = xbmcvfs.File("special://profile/addon_data/plugin.program.xmltv.meld/channels.m3u8",'w')
    f.write('#EXTM3U\n\n')
    f.write('\n'.join(streams).encode("utf8"))
    f.write('\n')
    f.close()

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
        zap_channels = plugin.get_storage('zap_channels')
        all_channels = dict(channels.items())
        all_channels.update(dict(zap_channels.items()))
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


@plugin.route('/add_channel/<name>/<id>')
def add_channel(name,id):
    name = name.decode("utf")
    id = id.decode("utf8")

    channels = plugin.get_storage('channels')
    channels[id] = name

    add_json_channel(id)


@plugin.route('/delete_channel/<id>')
def delete_channel(id):
    id = id.decode("utf8")

    channels = plugin.get_storage('channels')
    if id in channels:
        del channels[id]

    delete_json_channel(id)


@plugin.route('/rename_channel_id/<id>')
def rename_channel_id(id):
    id = id.decode("utf8")

    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    new_id = xbmcgui.Dialog().input(id,new_id)
    if new_id:
        ids[id] = new_id
    elif id in ids:
        del ids[id]

@plugin.route('/rename_channel/<id>')
def rename_channel(id):
    id = id.decode("utf8")

    channels = plugin.get_storage('channels')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]


@plugin.route('/add_zap/<name>/<url>')
def add_zap(name,url):
    zaps = plugin.get_storage('zaps')
    zaps[url] = name


@plugin.route('/delete_zap/<url>')
def delete_zap(url):
    zaps = plugin.get_storage('zaps')
    if url in zaps:
        del zaps[url]


@plugin.route('/delete_zap_channel/<id>')
def delete_zap_channel(id):
    id = id.decode("utf8")

    channels = plugin.get_storage('zap_channels')
    if id in channels:
        del channels[id]

    delete_json_channel(id)


@plugin.route('/rename_zap_channel_id/<id>')
def rename_zap_channel_id(id):
    id = id.decode("utf8")

    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    new_id = xbmcgui.Dialog().input(id,id)
    if new_id:
        ids[id] = new_id
    elif id in ids:
        del ids[id]


@plugin.route('/rename_zap_channel/<id>')
def rename_zap_channel(id):
    id = id.decode("utf8")

    zap_channels = plugin.get_storage('zap_channels')
    names = plugin.get_storage('names')
    name = zap_channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]


@plugin.route('/add_zap_channel/<name>/<id>')
def add_zap_channel(name,id):
    name = name.decode("utf")
    id = id.decode("utf8")

    channels = plugin.get_storage('zap_channels')
    channels[id] = name

    add_json_channel(id)


@plugin.route('/add_all_channels/<url>')
def add_all_channels(url):
    select_channels(url,add_all=True)


@plugin.route('/delete_all_channels/<url>')
def delete_all_channels(url):
    select_channels(url,remove_all=True)


@plugin.route('/select_channels/<url>')
def select_channels(url, add_all=False, remove_all=False):
    icons = plugin.get_storage('icons')

    if '\\' in url:
        url = url.replace('\\','/')
    filename = xbmc.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])
    xbmcvfs.copy(url,filename)

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
    channels = plugin.get_storage('channels')

    match = re.findall('<channel(.*?)</channel>', data.decode("utf8"), flags=(re.I|re.DOTALL))
    if match:

        for m in match:
            id = re.search('id="(.*?)"', m)
            if id:
                id = htmlparser.unescape(id.group(1))

            name = re.search('<display-name.*?>(.*?)</display-name', m)
            if name:
                name = htmlparser.unescape(name.group(1))

            icon = re.search('<icon.*?src="(.*?)"', m)
            if icon:
                icon = icon.group(1)

            if add_all == True:
                add_channel(name.encode("utf8"), id.encode("utf8"))
            if remove_all == True:
                delete_channel(id.encode("utf8"))

            context_items = []
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_channel',name=name.encode("utf8"), id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

            if id in channels:
                label = "[COLOR yellow]%s[/COLOR]" % name
            else:
                label = name

            icons[id] = icon

            items.append(
            {
                'label': label,
                'path': plugin.url_for('add_channel',name=name.encode("utf8"), id=id.encode("utf8")),
                'thumbnail':icon,
                'context_menu': context_items,
            })

    return sorted(items, key = lambda x: remove_formatting(x['label']))


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
            context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=name, url=url))))
            label = name
        else:
            context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % name
        context_items.append(("[COLOR yellow]Remove xmltv url[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_custom_xmltv, url=url))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items

@plugin.route('/rytec_xmltv')
def rytec_xmltv():

    sources = xbmcvfs.File("http://rytecepg.ipservers.eu/epg_data/rytec.King.sources.xml","r").read()

    urls = re.findall('<source.*?channels="(.*?)">.*?<description>(.*?)</description>.*?<url>(.*?)<',sources,flags=(re.I|re.DOTALL))

    items = []
    xmltv = plugin.get_storage('xmltv')
    for channels,description,url in sorted(urls,key=lambda x: x[1]):

        context_items = []
        if url not in xmltv:
            context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url),
            'thumbnail':get_icon_path('tv'),
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
            context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return sorted(items, key = lambda x: remove_formatting(x["label"]))


@plugin.route('/add_all_zap_channels/<country>/<zipcode>/<device>/<lineup>/<headend>')
def add_all_zap_channels(country, zipcode, device, lineup, headend):
    select_zap_channels(country, zipcode, device, lineup, headend, add_all=True)


@plugin.route('/delete_all_zap_channels/<country>/<zipcode>/<device>/<lineup>/<headend>')
def delete_all_zap_channels(country, zipcode, device, lineup, headend):
    select_zap_channels(country, zipcode, device, lineup, headend, remove_all=True)


@plugin.route('/select_zap_channels/<country>/<zipcode>/<device>/<lineup>/<headend>')
def select_zap_channels(country, zipcode, device, lineup, headend, add_all=False, remove_all=False):
    icons = plugin.get_storage('icons')

    gridtime = (int(time.mktime(time.strptime(str(datetime.datetime.now().replace(microsecond=0,second=0,minute=0)), '%Y-%m-%d %H:%M:%S'))))

    url = 'http://tvlistings.gracenote.com/api/grid?lineupId='+lineup+'&timespan=3&headendId=' + headend + '&country=' + country + '&device=' + device + '&postalCode=' + zipcode + '&time=' + str(gridtime) + '&pref=-&userId=-'
    data = xbmcvfs.File(url,'r').read()
    j = json.loads(data)
    channels = j.get('channels')

    items = []
    zap_channels = plugin.get_storage('zap_channels')


    for channel in channels:
        name = channel.get('callSign')
        id = channel.get('id')
        icon = "http:" + channel.get('thumbnail').replace('?w=55','')

        if add_all == True:
            add_zap_channel(name.encode("utf8"), id.encode("utf8"))
        if remove_all == True:
            delete_zap_channel(id.encode("utf8"))

        context_items = []
        context_items.append(("[COLOR yellow]Remove channel[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap_channel, id=id.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_zap_channels',country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_zap_channels, country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))

        if id in zap_channels:
            label = "[COLOR yellow]%s[/COLOR]" % name
        else:
            label = name

        icons[id] = icon

        items.append(
        {
            'label': label,
            'path': plugin.url_for('add_zap_channel',name=name.encode("utf8"), id=id.encode("utf8")),
            'thumbnail':icon,
            'context_menu': context_items,
        })

    return items


@plugin.route('/zap')
def zap():
    items = []

    for label, country in [("Canada","CAN"), ("USA","USA")]:

        context_items = []

        items.append(
        {
            'label': label,
            'path': plugin.url_for('zap_country',country=country),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items


@plugin.route('/zap_country/<country>')
def zap_country(country):
    zaps = plugin.get_storage('zaps')

    zipcode = plugin.get_setting('zap.' + country.lower() + '.zipcode')

    url = 'https://tvlistings.gracenote.com/gapzap_webapi/api/Providers/getPostalCodeProviders/' + country + '/' + zipcode + '/gapzap'

    sources = xbmcvfs.File(url,"r").read()

    j = json.loads(sources)
    providers = j.get('Providers')

    items = []

    if country == "USA":
        lineupsN = ['TIMEZONE - Eastern', 'TIMEZONE - Central', 'TIMEZONE - Mountain', 'TIMEZONE - Pacific', 'TIMEZONE - Alaskan', 'TIMEZONE - Hawaiian']
        lineupsC = ['DFLTE', 'DFLTC', 'DFLTM', 'DFLTP', 'DFLTA', 'DFLTH']
    else:
        lineupsN = ['TIMEZONE - Eastern', 'TIMEZONE - Central', 'TIMEZONE - Mountain', 'TIMEZONE - Pacific']
        lineupsC = ['DFLTEC', 'DFLTCC', 'DFLTMC', 'DFLTPC']

    for name,lineup in zip(lineupsN,lineupsC):

        device = '-'
        headend = lineup

        #label = "%s / %s / %s / %s" % (name,device,lineup,headend)
        label = name

        url = 'http://tvlistings.gracenote.com/api/grid?lineupId='+lineup+'&timespan=3&headendId=' + headend + '&country=' + country + '&device=' + device + '&postalCode=' + zipcode  + '&pref=-&userId=-'

        context_items = []
        if url not in zaps:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add zap", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_zap, name=name, url=url))))
            label = label
        else:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove zap", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % label
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_zap_channels',country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_zap_channels, country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_zap_channels',country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    for provider in sorted(providers, key=lambda x: x['name']):

        name = provider.get('name')
        device = provider.get('device') or '-'
        lineup = provider.get('lineupId') or '-'
        headend = provider.get('headendId') or '-'

        #label = "%s / %s / %s / %s" % (name,device,lineup,headend)
        label = name

        url = 'http://tvlistings.gracenote.com/api/grid?lineupId='+lineup+'&timespan=3&headendId=' + headend + '&country=' + country + '&device=' + device + '&postalCode=' + zipcode  + '&pref=-&userId=-'

        context_items = []
        if url not in zaps:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add zap", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_zap, name=name, url=url))))
            label = label
        else:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove zap", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % label
        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_zap_channels',country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items



@plugin.route('/sort_channels')
def sort_channels():
    channels = plugin.get_storage('channels')

    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            order = json.loads(data)
        else:
            order = []
        f.close()
    else:
        order = []

    order.sort(key=lambda k: channels[k].lower())

    f = xbmcvfs.File(path,'w')
    f.write(json.dumps(order,indent=0))


@plugin.route('/move_channel/<id>')
def move_channel(id):
    channels = plugin.get_storage('channels')
    zap_channels = plugin.get_storage('zap_channels')

    all_channels = dict(channels.items())
    all_channels.update(dict(zap_channels.items()))

    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            order = json.loads(data)
        else:
            order = []
        f.close()
    else:
        order = []

    sorted_channels_names = [all_channels[x] for x in order]

    dialog = xbmcgui.Dialog()

    index = dialog.select('%s: Move After?' % all_channels[id], sorted_channels_names)
    if index == -1:
        return

    oldindex = order.index(id)
    order.insert(index+1, order.pop(oldindex))

    f = xbmcvfs.File(path,'w')
    f.write(json.dumps(order,indent=0))

    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/channels')
def channels():
    channels = plugin.get_storage('channels')
    zap_channels = plugin.get_storage('zap_channels')
    names = plugin.get_storage('names')

    all_channels = dict(channels.items())
    all_channels.update(dict(zap_channels.items()))

    icons = plugin.get_storage('icons')

    path = profile()+'id_order.json'
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path,'r')
        data = f.read()
        if data:
            order = json.loads(data)
        else:
            order = []
        f.close()
    else:
        order = []

    items = []
    for id in order:
        name = all_channels.get(id)
        if not name:
            continue
        name = names.get(id,name)

        context_items = []
        if id in zap_channels:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove zap channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change zap channel id", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_zap_channel_id, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename zap channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_zap_channel, id=id.encode("utf8")))))
        if id in channels:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change channel id", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel_id, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel, id=id.encode("utf8")))))

        items.append(
        {
            'label': name,
            'path': plugin.url_for('move_channel',id=id),
            'thumbnail': icons.get(id, get_icon_path('tv')),
            'context_menu': context_items,
        })

    return items


@plugin.route('/')
def index():
    items = []

    items.append(
    {
        'label': "Custom",
        'path': plugin.url_for('custom_xmltv'),
        'thumbnail':get_icon_path('tv'),
    })

    items.append(
    {
        'label': "Rytec",
        'path': plugin.url_for('rytec_xmltv'),
        'thumbnail':get_icon_path('tv'),
    })

    items.append(
    {
        'label': "koditvepg.com",
        'path': plugin.url_for('koditvepg_xmltv'),
        'thumbnail':get_icon_path('tv'),
    })

    items.append(
    {
        'label': "Zap",
        'path': plugin.url_for('zap'),
        'thumbnail':get_icon_path('tv'),
    })

    context_items = []
    context_items.append(('Sort Channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for('sort_channels'))))
    items.append(
    {
        'label': 'Re-order Channels',
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
    items.append(
    {
        'label': "Reset",
        'path': plugin.url_for('reset'),
        'thumbnail':get_icon_path('settings'),
    })
    return items


if __name__ == '__main__':
    create_json_channels()
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)
        #plugin.set_view_mode(51)
        #pass
    #plugin.set_content("files")