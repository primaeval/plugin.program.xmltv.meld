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
from rpc import RPC

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
    streams = plugin.get_storage('streams')
    radio = plugin.get_storage('radio')

    m3u_streams = {}
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
                    if radio.get(id):
                        group = name+" Radio"
                        radio_flag = 'radio="true" '
                    else:
                        group = name
                        radio_flag = ''
                    m3u_streams[id] ='#EXTINF:-1 %stvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (radio_flag,callSign,id,thumbnail,group,callSign,streams.get(id,'http://localhost'))

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

    return selected_channels,selected_programmes,m3u_streams


@plugin.route('/update')
def update():
    xbmcgui.Dialog().notification("xmltv Meld","update starting",sound=False)

    xmltv = plugin.get_storage('xmltv')
    channels = plugin.get_storage('channels')
    streams = plugin.get_storage('streams')
    radio = plugin.get_storage('radio')
    ids = plugin.get_storage("ids")
    names = plugin.get_storage("names")

    m3u_streams = {}
    selected_channels = {}
    selected_programmes = []

    htmlparser = HTMLParser()

    for url in xmltv:

        group = xmltv[url]

        if '\\' in url:
            url = url.replace('\\','/')

        filename = xbmc.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])
        success = xbmcvfs.copy(url,filename)
        if not success:
            url2 = url.replace('koditvepg.com','koditvepg2.com')
            success = xbmcvfs.copy(url2,filename)
            if not success:
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
                data = xbmcvfs.File(filename,'r').read()
            else:
                f = open(filename,'r')
                data = f.read()
                f.close()

        encoding = re.search('encoding="(.*?)"',data)
        if encoding:
            encoding = encoding.group(1)

        xchannels = re.findall('(<channel.*?</channel>)', data, flags=(re.I|re.DOTALL))
        xprogrammes = re.findall('(<programme.*?</programme>)', data, flags=(re.I|re.DOTALL))

        for channel in xchannels:
            if encoding:
                channel = channel.decode(encoding)
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
                if radio.get(id):
                    group_label = group+" Radio"
                    radio_flag = 'radio="true" '
                else:
                    group_label = group
                    radio_flag = ''
                m3u_streams[id] = '#EXTINF:-1 %stvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (radio_flag,name,ids.get(id,id),icon,group_label,name,streams.get(id,'http://localhost'))

        for programme in xprogrammes:
            if encoding:
                programme = programme.decode(encoding)
            id = re.search('channel="(.*?)"', programme)
            if id:
                id = htmlparser.unescape(id.group(1))

                if id in channels:
                    selected_programmes.append(programme)

    zap_channels, zap_programmes, zap_m3u_streams = update_zap()
    selected_channels.update(zap_channels)
    selected_programmes = selected_programmes + zap_programmes
    m3u_streams.update(zap_m3u_streams)

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

    sorted_streams = []
    for id in channel_order:
        sorted_streams.append(m3u_streams[id])


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
    for programme in new_selected_programmes:
        f.write(programme.encode("utf8")+'\n\n')
    f.write('\n')
    f.write('</tv>\n')
    f.close()

    f = xbmcvfs.File("special://profile/addon_data/plugin.program.xmltv.meld/channels.m3u8",'w')
    f.write('#EXTM3U\n\n')
    f.write('\n'.join(sorted_streams).encode("utf8"))
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
    name = decode(name)
    id = decode(id)

    channels = plugin.get_storage('channels')
    channels[id] = name

    add_json_channel(id)


@plugin.route('/delete_channel/<id>')
def delete_channel(id):
    id = decode(id)

    channels = plugin.get_storage('channels')
    if id in channels:
        del channels[id]

    delete_json_channel(id)


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


@plugin.route('/rename_channel/<id>')
def rename_channel(id):
    id = decode(id)

    channels = plugin.get_storage('channels')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/radio_stream/<id>')
def radio_stream(id):
    id = decode(id)
    channels = plugin.get_storage('channels')
    radio_stream_dialog(id,channels)


@plugin.route('/zap_radio_stream/<id>')
def zap_radio_stream(id):
    id = decode(id)
    channels = plugin.get_storage('zap_channels')
    radio_stream_dialog(id,channels)


def radio_stream_dialog(id,channels):
    radio = plugin.get_storage('radio')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)
    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    radio[id] = xbmcgui.Dialog().yesno(new_name,"Radio?")


@plugin.route('/channel_stream/<id>')
def channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('channels')
    channel_stream_dialog(id,channels)


@plugin.route('/zap_channel_stream/<id>')
def zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap_channels')
    channel_stream_dialog(id,channels)


def channel_stream_dialog(id,channels):
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)
    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    addons = get_addons()

    addon_names = [x["name"] for x in addons]

    index = xbmcgui.Dialog().select("Stream: %s [%s]" % (new_name,new_id), addon_names )

    if index == -1:
        return
    addon = addons[index]

    addonid = addon['addonid']
    path = "plugin://%s" % addonid


    while True:
        dirs,files = get_folder(path)

        all = [("dir",x,"[B]%s[/B]" % dirs[x]) for x in sorted(dirs,key=lambda k: dirs[k])]
        all = all + [("file",x,files[x]) for x in sorted(files,key=lambda k: files[k])]

        labels = [x[2] for x in all]

        index = xbmcgui.Dialog().select("Stream: %s [%s]" % (new_name,new_id), labels )
        if index == None:
            return
        type,path,label = all[index]

        if type == "file":
            streams[id] = path
            break


@plugin.route('/guess_channel_stream/<id>')
def guess_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('channels')
    guess_channel_stream_dialog(id,channels)


@plugin.route('/guess_zap_channel_stream/<id>')
def guess_zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap_channels')
    guess_channel_stream_dialog(id,channels)


def guess_channel_stream_dialog(id,channels):
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)
    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    folders = plugin.get_storage('folders')
    paths = plugin.get_storage('paths')

    exact = []
    partial = []
    other = []
    for folder in folders:
        addon = folders[folder]
        addon_label = paths["plugin://"+addon]
        folder_label = paths[folder]
        dirs,files = get_folder(folder)
        for file in files:
            label = files[file]
            new_name_match = re.sub(" hd$",'',new_name.lower())
            if new_name_match == label.lower():
                exact.append(("exact","[COLOR yellow]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))
            elif new_name_match in label.lower():
                partial.append(("partial","[COLOR orange]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))
            else:
                other.append(("other",label,addon,addon_label,folder,folder_label,file))

    all = sorted(exact,key=lambda k: k[1]) + sorted(partial,key=lambda k: k[1]) + sorted(other,key=lambda k: k[1])
    labels = ["%s - %s" % (x[3],x[1]) for x in all]

    index = xbmcgui.Dialog().select("Stream: %s [%s]" % (new_name,new_id), labels )
    if index == -1:
        return
    (type,label,addon,addon_label,folder,folder_label,file) = all[index]
    streams[id] = file


@plugin.route('/paste_channel_stream/<id>')
def paste_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('channels')
    paste_channel_stream_dialog(id,channels)


@plugin.route('/paste_zap_channel_stream/<id>')
def paste_zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap_channels')
    paste_channel_stream_dialog(id,channels)


def paste_channel_stream_dialog(id,channels):
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)
    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    url = xbmcgui.Dialog().input("Stream Url: %s [%s]" % (new_name,new_id))

    if url == None:
        return
    streams[id] = url


@plugin.route('/get_addons')
def get_addons():
    all_addons = []
    for type in ["xbmc.addon.video","xbmc.addon.audio"]:
        try: response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail"])
        except: continue
        if "addons" in response:
            found_addons = response["addons"]
            all_addons = all_addons + found_addons

    seen = set()
    addons = []
    for addon in all_addons:
        if addon['addonid'] not in seen:
            addons.append(addon)
        seen.add(addon['addonid'])

    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    return addons


@plugin.route('/get_folder/<path>')
def get_folder(path):
    try: response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except: return
    all = response["files"]
    dirs = {f["file"]:remove_formatting(f["label"]) for f in all if f["filetype"] == "directory"}
    files = {f["file"]:remove_formatting(f["label"]) for f in all if f["filetype"] == "file"}
    return dirs,files


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
    id = decode(id)

    channels = plugin.get_storage('zap_channels')
    if id in channels:
        del channels[id]

    delete_json_channel(id)


@plugin.route('/rename_zap_channel_id/<id>')
def rename_zap_channel_id(id):
    id = decode(id)

    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    new_id = xbmcgui.Dialog().input(id,id)
    if new_id:
        ids[id] = new_id
    elif id in ids:
        del ids[id]


@plugin.route('/rename_zap_channel/<id>')
def rename_zap_channel(id):
    id = decode(id)

    zap_channels = plugin.get_storage('zap_channels')
    names = plugin.get_storage('names')
    name = zap_channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_zap_channel/<name>/<id>')
def add_zap_channel(name,id):
    name = name.decode("utf")
    id = decode(id)

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
    success = xbmcvfs.copy(url,filename)
    if not success:
        url2 = url.replace('koditvepg.com','koditvepg2.com')
        success = xbmcvfs.copy(url2,filename)
        if not success:
            return

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

    match = re.findall('<channel(.*?)</channel>', decode(data), flags=(re.I|re.DOTALL))
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

    sources = xbmcvfs.File("http://rytecepg.epgspot.com/epg_data/rytec.King.sources.xml","r").read()

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

    urls = {'http://epg.koditvepg2.com/AT/guide.xml.gz': 'Austria', 'http://epg.koditvepg2.com/PL/guide.xml.gz': 'Poland', 'http://epg.koditvepg2.com/TR/guide.xml.gz': 'Turkey', 'http://epg.koditvepg2.com/IN/guide.xml.gz': 'India', 'http://epg.koditvepg2.com/FI/guide.xml.gz': 'Finland', 'http://epg.koditvepg2.com/SK/guide.xml.gz': 'Slovakia', 'http://epg.koditvepg2.com/CN/guide.xml.gz': 'China', 'http://epg.koditvepg2.com/NL/guide.xml.gz': 'Netherlands', 'http://epg.koditvepg2.com/GE/guide.xml.gz': 'Georgia', 'http://epg.koditvepg2.com/LU/guide.xml.gz': 'Luxembourg', 'http://epg.koditvepg2.com/SE/guide.xml.gz': 'Sweden', 'http://epg.koditvepg2.com/RU/guide.xml.gz': 'Russia', 'http://epg.koditvepg2.com/AU/guide.xml.gz': 'Australia', 'http://epg.koditvepg2.com/IS/guide.xml.gz': 'Iceland', 'http://epg.koditvepg2.com/AR/guide.xml.gz': 'Argentina', 'http://epg.koditvepg2.com/GB/guide.xml.gz': 'United Kingdom', 'http://epg.koditvepg2.com/RO/guide.xml.gz': 'Romania', 'http://epg.koditvepg2.com/ME/guide.xml.gz': 'Montenegro', 'http://epg.koditvepg2.com/NZ/guide.xml.gz': 'New Zealand', 'http://epg.koditvepg2.com/DE/guide.xml.gz': 'Germany', 'http://epg.koditvepg2.com/DO/guide.xml.gz': 'Dominican Rep.', 'http://epg.koditvepg2.com/BR/guide.xml.gz': 'Brazil', 'http://epg.koditvepg2.com/TH/guide.xml.gz': 'Thailand', 'http://epg.koditvepg2.com/DK/guide.xml.gz': 'Denmark', 'http://epg.koditvepg2.com/PH/guide.xml.gz': 'Philippines', 'http://epg.koditvepg2.com/AL/guide.xml.gz': 'Albania', 'http://epg.koditvepg2.com/PR/guide.xml.gz': 'Puerto Rico', 'http://epg.koditvepg2.com/RS/guide.xml.gz': 'Serbia', 'http://epg.koditvepg2.com/GR/guide.xml.gz': 'Greece', 'http://epg.koditvepg2.com/PA/guide.xml.gz': 'Panama', 'http://epg.koditvepg2.com/IE/guide.xml.gz': 'Ireland', 'http://epg.koditvepg2.com/TW/guide.xml.gz': 'Taiwan', 'http://epg.koditvepg2.com/JP/guide.xml.gz': 'Japan', 'http://epg.koditvepg2.com/MX/guide.xml.gz': 'Mexico', 'http://epg.koditvepg2.com/FR/guide.xml.gz': 'France', 'http://epg.koditvepg2.com/AE/guide.xml.gz': 'United Arab Emirates', 'http://epg.koditvepg2.com/MK/guide.xml.gz': 'Macedonia', 'http://epg.koditvepg2.com/HU/guide.xml.gz': 'Hungary', 'http://epg.koditvepg2.com/IL/guide.xml.gz': 'Israel', 'http://epg.koditvepg2.com/SA/guide.xml.gz': 'Saudi Arabia', 'http://epg.koditvepg2.com/UA/guide.xml.gz': 'Ukraine', 'http://epg.koditvepg2.com/PK/guide.xml.gz': 'Pakistan', 'http://epg.koditvepg2.com/LT/guide.xml.gz': 'Lithuania', 'http://epg.koditvepg2.com/KZ/guide.xml.gz': 'Kazakhstan', 'http://epg.koditvepg2.com/LV/guide.xml.gz': 'Latvia', 'http://epg.koditvepg2.com/BE/guide.xml.gz': 'Belgium', 'http://epg.koditvepg2.com/PT/guide.xml.gz': 'Portugal', 'http://epg.koditvepg2.com/CA/guide.xml.gz': 'Canada', 'http://epg.koditvepg2.com/VN/guide.xml.gz': 'Vietnam', 'http://epg.koditvepg2.com/HR/guide.xml.gz': 'Croatia', 'http://epg.koditvepg2.com/ES/guide.xml.gz': 'Spain', 'http://epg.koditvepg2.com/CZ/guide.xml.gz': 'Czech Rep.', 'http://epg.koditvepg2.com/EG/guide.xml.gz': 'Egypt', 'http://epg.koditvepg2.com/BG/guide.xml.gz': 'Bulgaria', 'http://epg.koditvepg2.com/CO/guide.xml.gz': 'Colombia', 'http://epg.koditvepg2.com/US/guide.xml.gz': 'United States', 'http://epg.koditvepg2.com/NO/guide.xml.gz': 'Norway', 'http://epg.koditvepg2.com/BA/guide.xml.gz': 'Bosnia and Herz.', 'http://epg.koditvepg2.com/CH/guide.xml.gz': 'Switzerland', 'http://epg.koditvepg2.com/IT/guide.xml.gz': 'Italy', 'http://epg.koditvepg2.com/SI/guide.xml.gz': 'Slovenia', 'http://epg.koditvepg2.com/XK/guide.xml.gz': 'Kosovo'}

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
    zap_channels = plugin.get_storage('zap_channels')
    all_channels = channels.raw_dict()
    all_channels.update(zap_channels.raw_dict())

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

    order.sort(key=lambda k: all_channels[k][0].lower())

    f = xbmcvfs.File(path,'w')
    f.write(json.dumps(order,indent=0))


@plugin.route('/move_channel/<id>')
def move_channel(id):
    id = decode(id)
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
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove Zap Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change Zap Channel Id", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_zap_channel_id, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename Zap Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_zap_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Channel Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(zap_channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Guess Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(guess_zap_channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Paste Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(paste_zap_channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Radio", 'XBMC.RunPlugin(%s)' % (plugin.url_for(zap_radio_stream, id=id.encode("utf8")))))
        if id in channels:
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change Channel Id", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel_id, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Channel Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Guess Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(guess_channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Paste Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(paste_channel_stream, id=id.encode("utf8")))))
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Radio", 'XBMC.RunPlugin(%s)' % (plugin.url_for(radio_stream, id=id.encode("utf8")))))

        items.append(
        {
            'label': name,
            'path': plugin.url_for('move_channel',id=id.encode("utf8")),
            'thumbnail': icons.get(id, get_icon_path('tv')),
            'context_menu': context_items,
        })

    return items

@plugin.route('/folders_paths/<id>/<path>')
def folders_paths(id,path):
    folders = plugin.get_storage('folders')
    paths = plugin.get_storage('paths')
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

    items = []

    for folder_path in sorted(dirs,key=lambda k: dirs[k].lower()):
        label = dirs[folder_path]
        paths[folder_path] = label
        context_items = []
        if path in folders:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=folder_path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=folder_path))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folders_paths',id=id, path=folder_path),
            'thumbnail': get_icon_path('tv'),
            'context_menu': context_items,
        })

    for url in sorted(links):
        items.append(
        {
            'label': links[url],
            'path': url,
            'thumbnail': thumbnails[url],
            'is_playable': True,
            'info_type': 'Video',
            'info':{"mediatype": "movie", "title": links[url]}
        })
    return items

@plugin.route('/add_folder/<id>/<path>')
def add_folder(id,path):
    folders = plugin.get_storage('folders')
    folders[path] = id
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/remove_folder/<id>/<path>')
def remove_folder(id,path):
    folders = plugin.get_storage('folders')
    del folders[path]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_folders')
def remove_folders():
    folders = plugin.get_storage('folders')
    paths = plugin.get_storage('paths')

    folder_label = [(f,paths.get(f,folders[f])) for f in sorted(folders,key=lambda k: folders[k])]
    labels = [f[1] for f in folder_label]

    indexes = xbmcgui.Dialog().multiselect("Remove Folders",labels)
    if indexes:
        for index in sorted(indexes, reverse=True):
            url = folder_label[index][0]
            del folders[url]



@plugin.route('/play/<url>')
def play(url):
    #BUG: Leia
    xbmc.executebuiltin('PlayMedia(%s)' % url)

@plugin.route('/folders_addons')
def folders_addons():
    folders = plugin.get_storage('folders')
    paths = plugin.get_storage('paths')
    ids = {}
    for folder in folders:
        id = folders[folder]
        ids[id] = id
    all_addons = []
    for type in ["xbmc.addon.video", "xbmc.addon.audio"]:
        try: response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail"])
        except: continue
        if "addons" in response:
            found_addons = response["addons"]
            all_addons = all_addons + found_addons

    seen = set()
    addons = []
    for addon in all_addons:
        if addon['addonid'] not in seen:
            addons.append(addon)
        seen.add(addon['addonid'])

    items = []

    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    for addon in addons:
        label = remove_formatting(addon['name'])
        id = addon['addonid']
        path = "plugin://%s" % id
        paths[path] = label
        context_items = []
        if id in ids:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folders_paths',id=id, path=path),
            'thumbnail': get_icon_path('tv'),
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
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Sort Channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for('sort_channels'))))
    items.append(
    {
        'label': 'Channels',
        'path': plugin.url_for('channels'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    context_items = []
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_folders'))))
    items.append(
    {
        'label': 'Folders',
        'path': plugin.url_for('folders_addons'),
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