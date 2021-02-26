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



class Yo:

    def __init__(self):
        self._channels = {}
        self._countries = {}

    def get_url(self,url):
        #headers = {'user-agent': 'Mozilla/5.0 (BB10; Touch) AppleWebKit/537.10+ (KHTML, like Gecko) Version/10.0.9.2372 Mobile Safari/537.10+'}
        headers = {'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'}
        try:
            r = requests.get(url,headers=headers)
            #log(r)
            #log(r.content)
            #log(r.text)
            return r.text
            #html = HTMLParser.HTMLParser().unescape(r.content.decode('utf-8'))
            #log(html)
            #return html
        except:
            return ''


    def select_provider(self,country):
        d = xbmcgui.Dialog()

        if country == "uk":
            url = "http://uk.yo.tv/api/setting?id=1594745998&lookupid=3"
        else:
            result = d.input("%s: zip/post code" % country)
            if not result:
                return
            url = "http://%s.yo.tv/api/setting?id=%s" % (country,result)

        #log(url)
        j = self.get_url(url)
        if not j:
            return
        data = json.loads(j)
        providers = [x["Name"] for x in data]
        index = d.select("%s provider:" % country,providers)
        if index == -1:
            return
        headend = data[index]["Value"]
        if headend:
            yo_headends = plugin.get_storage('yo_headends')
            yo_headends[country] = headend


    def countries(self):
        htmlparser = HTMLParser()
        #sources = xbmcvfs.File("http://yo.tv/","r").read()
        sources = requests.get("http://yo.tv/").content.decode('utf-8')

        match = re.findall('<li><a href="http://(.*?)\.yo\.tv"  >(.*?)</a></li>',sources)
        self._countries = {m[0]:html.unescape(m[1]) for m in match}

        return sorted(list(self._countries.items()), key=operator.itemgetter(1))


    def channels(self,country):
        session = requests.Session()

        yo_headends = plugin.get_storage('yo_headends')
        headend = yo_headends.get(country)
        if headend:
            r = session.get('http://%s.yo.tv/settings/headend/%s' % (country,headend))

        url = "http://%s.yo.tv" % country

        data = session.get(url).text
        soup = BeautifulSoup(data, "html.parser")
        x = soup.select("#channelbar")
        li_img = x[0].select("li")

        ul = soup.select("#content ul")[0]
        li = ul.find_all("li",recursive=False)
        #log(li)
        ids = [l["id"] for l in li]
        #log(ids)

        #log((len(ids),len(li_img)))

        channel_list = []
        for i,img in enumerate(li_img):
            im = img.find("img",recursive=False)
            if not im:
                h2 = img.find("h2",recursive=False)
                name = h2.get_text().strip()
                thumbnail = get_icon_path("tv")
                #number = "-1"
            else:
                name = im["alt"]
                thumbnail  = im["data-original"]
                #number = im.parent.get_text().strip()
            channel_list.append({
                "name" : name,
                "id": ids[i],
                "thumbnail" : thumbnail,

            })
        self._channels[country] = channel_list
        return channel_list

    def all_channels(self):
        self.countries()
        channels = plugin.get_storage('yo_channels')
        all = []
        for id,(country,name,thumbnail) in list(channels.items()):
            all.append({
                "id": id,
                "name": name,
                "thumbnail": thumbnail,
                "provider": "yo",
                "country": self._countries.get(country,country),
            })
        return all


    def add_channel(self,country,id,name,thumbnail):
        channels = plugin.get_storage('yo_channels')
        channels[id] = (country,name,thumbnail)


    def delete_channel(self,id):
        channels = plugin.get_storage('yo_channels')
        if id in channels:
            del channels[id]


    def add_all_channels(self,country):
        channels = plugin.get_storage('yo_channels')

        for c in self.channels(country):
            self.add_channel(country,c["id"],c["name"],c["thumbnail"])


    def delete_all_channels(self,country):
        channels = plugin.get_storage('yo_channels')
        for id,(ccountry,name,thumbnail) in list(channels.items()):
            #ccountry,name,thumbnail = channels[id]
            if country == ccountry:
                del channels[id]


    def update(self):
        yo_channels = plugin.get_storage('yo_channels')
        streams = plugin.get_storage('streams')
        names = plugin.get_storage('names')
        ids = plugin.get_storage('ids')

        self.countries()

        countries = collections.defaultdict(list)
        for id,(country,name,thumbnail) in yo_channels.items():
            countries[country].append((name,id,thumbnail))

        channel_xml = {}
        m3u_streams = {}


        for country in countries:
            for name,id,thumbnail in countries[country]:

                xchannel = '<channel id="%s">\n' % (ids.get(id,id))
                xchannel += '\t<display-name>' + escape(names.get(id,name)) + '</display-name>\n'
                if thumbnail:
                    xchannel += '\t<icon src="' + thumbnail + '"/>\n'
                xchannel += '</channel>'
                channel_xml[id] = xchannel

                radio_flag = ''
                m3u_streams[id] = '#EXTINF:-1 %stvg-name="%s" tvg-id="%s" tvg-logo="%s" group-title="%s",%s\n%s\n' % (radio_flag,names.get(id,name),ids.get(id,id),thumbnail,self._countries[country],name,streams.get(id,'http://localhost'))


        programmes = []
        programme_xml = []
        for country in countries:
            for name,id,thumbnail in countries[country]:
                for day in range(plugin.get_setting('yo.days',int)):
                    offset = divmod(-time.timezone,3600)
                    offset_str = "%02d.%02d" % (abs(offset[0]),offset[1])
                    if offset[0] >= 0:
                        offset = "+"+offset_str
                    else:
                        offset = "-"+offset_str

                    url = "http://%s.yo.tv/api/GS?cid=%s&offset=%s&day=%s" % (country,id,offset,day)
                    #log(url)
                    data = requests.get(url).json()
                    #log(data)

                    now = datetime.datetime.now()
                    for li in data:
                        #log(li)
                        soup = BeautifulSoup(li,'html.parser')
                        a = soup.find_all('a',recursive=False)
                        last_time = datetime.datetime(year=1900,month=1,day=1)
                        for aa in a:
                            start = aa["data-time"]
                            #log(start)
                            hour_minute,am_pm = start.split()
                            hour,minute = hour_minute.split(":")
                            hour = int(hour)
                            minute=int(minute)
                            if am_pm == "pm" and hour != 12:
                                hour += 12
                            elif am_pm == "am" and hour == 12:
                                hour = 0

                            start = now.replace(hour=hour,minute=minute,second=0,microsecond=0) + datetime.timedelta(days=day)
                            if start < last_time:
                                start += datetime.timedelta(days=1)
                            last_time = start

                            flags = aa["data-flags"]
                            stop = start
                            match = re.search('(\d+) minutes',flags)
                            if match:
                                stop = start + datetime.timedelta(minutes=int(match.group(1)))

                            #log(start)
                            h2 = aa.find('h2',recursive=False)
                            #log(h2)
                            title = h2.get_text().strip()
                            #log(title)
                            h3 = aa.find('h3',recursive=False)
                            #log(h3)
                            description = h3.get_text().strip()
                            #log(description)
                            #log((start,stop,title,description))
                            tuple = (start,stop,title,description)
                            if tuple not in programmes:
                                programmes.append(tuple)
                                start = start.strftime("%Y%m%d%H%M%S")
                                stop = stop.strftime("%Y%m%d%H%M%S")
                                offset = divmod(-time.timezone,3600)
                                offset_str = "%02d%02d" % (abs(offset[0]),offset[1])
                                if offset[0] >= 0:
                                    offset = "+"+offset_str
                                else:
                                    offset = "-"+offset_str
                                programme = '<programme start="%s %s" stop="%s %s" channel="%s"><title>%s</title><desc>%s</desc></programme>' % (start,offset,stop,offset,ids.get(id,id),escape(title),escape(description))
                                #log(programme)
                                programme_xml.append(programme)


        return channel_xml,programme_xml,m3u_streams



@plugin.route('/yo')
def yo():
    yo_channels = plugin.get_storage('yo_channels')
    channel_countries = {yo_channels[x][0] for x in yo_channels}

    countries = Yo().countries()

    items = []

    for country,label in countries:
        context_items = []
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add All Channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('yo_add_all_channels',country=country))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove All Channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('yo_delete_all_channels',country=country))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Select Provider", 'XBMC.RunPlugin(%s)' % (plugin.url_for('yo_provider',country=country))))

        if country in channel_countries:
            label = "[COLOR yellow]%s[/COLOR]" % label

        items.append(
        {
            'label': label,
            'path': plugin.url_for('yo_select_channels',country=country),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items


@plugin.route('/yo_select_channels/<country>')
def yo_select_channels(country):
    yo_channels = plugin.get_storage('yo_channels')
    channels = Yo().channels(country)

    items = []
    for channel in channels:
        context_items = []
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Update", 'XBMC.RunPlugin(%s)' % (plugin.url_for('yo_update'))))

        #label = "%s %s" % (channel["id"],channel["name"])
        label = channel["name"]
        if channel["id"] in yo_channels:
            label = "[COLOR yellow]%s[/COLOR]" % label
            path = plugin.url_for('yo_delete_channel',id=channel["id"])
        else:
            path = plugin.url_for('yo_add_channel',country=country,name=channel["name"].encode("utf8"),id=channel["id"],thumbnail=channel["thumbnail"])

        items.append({
            "label": label, #"%s %s" % (channel["id"],channel["name"]),
            "thumbnail":channel["thumbnail"],
            "path": path,
            'context_menu': context_items,
        })
    return items


@plugin.route('/yo_delete_channel/<id>')
def yo_delete_channel(id):
    Yo().delete_channel(id)


@plugin.route('/yo_provider/<country>')
def yo_provider(country):
    Yo().select_provider(country)


@plugin.route('/yo_delete_all_channels/<country>')
def yo_delete_all_channels(country):
    Yo().delete_all_channels(country)


@plugin.route('/yo_add_channel/<country>/<id>/<name>/<thumbnail>')
def yo_add_channel(country,id,name,thumbnail):
    Yo().add_channel(country,id,name,thumbnail)


@plugin.route('/yo_add_all_channels/<country>')
def yo_add_all_channels(country):
    Yo().add_all_channels(country)


@plugin.route('/yo_update')
def yo_update():
    Yo().update()


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


@plugin.route('/update_zap')
def update_zap():
    zaps = plugin.get_storage('zaps')

    zap_channels = plugin.get_storage('zap2_channels')
    streams = plugin.get_storage('streams')
    radio = plugin.get_storage('radio')

    m3u_streams = {}
    selected_channels = {}
    selected_programmes = []

    gridtimeStart = (int(time.mktime(time.strptime(str(datetime.datetime.now().replace(microsecond=0,second=0,minute=0)), '%Y-%m-%d %H:%M:%S'))))

    for url,name in zaps.items():

        count = 0

        gridtime = gridtimeStart
        while count < (8 * int(plugin.get_setting('zap.days') or "1")):
            u = url + '&time=' + str(gridtime)
            #data = xbmcvfs.File(u,'r').read()
            data = requests.get(u).content
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


@plugin.route('/xml_update')
def xml_update():


    #xmltv = plugin.get_storage('xmltv')
    channels = plugin.get_storage('xml_channels')
    for channel in channels:
        data = list(channels[channel])
        data[0] = data[0].replace('http://rytecepg.dyndns.tv/~rytecepg/epg_data/','http://rytecepg.epgspot.com/epg_data/')
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
                f = open(filename,'r')
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
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
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

    yo_channel_xml,yo_programme_xml,yo_m3u_streams = Yo().update()
    xml_channel_xml,xml_programme_xml,xml_m3u_streams = xml_update()
    zap_channels, zap_programmes, zap_m3u_streams = update_zap()
    #log((zap_channels, zap_programmes, zap_m3u_streams))

    channel_xml = yo_channel_xml
    channel_xml.update(xml_channel_xml)
    channel_xml.update(zap_channels)
    programme_xml = yo_programme_xml + xml_programme_xml + zap_programmes
    m3u_streams = yo_m3u_streams
    m3u_streams.update(xml_m3u_streams)
    m3u_streams.update(zap_m3u_streams)

    order = plugin.get_storage('order')

    new_channel_xml = [channel_xml[id] for id in sorted(channel_xml, key=lambda k: order.get(k,-1))]


    f = xbmcvfs.File(xmltv_location()+"/xmltv.xml",'w')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
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
        zap_channels = plugin.get_storage('zap2_channels')
        all_channels = dict(list(channels.items()))
        all_channels.update(dict(list(zap_channels.items())))
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


@plugin.route('/radio_stream/<id>')
def radio_stream(id):
    id = decode(id)
    channels = plugin.get_storage('channels')
    radio_stream_dialog(id,channels)


@plugin.route('/zap_radio_stream/<id>')
def zap_radio_stream(id):
    id = decode(id)
    channels = plugin.get_storage('zap2_channels')
    radio_stream_dialog(id,channels)


def radio_stream_dialog(id,channels):
    radio = plugin.get_storage('radio')
    names = plugin.get_storage('names')
    name = channels[id]
    new_name = names.get(id,name)
    ids = plugin.get_storage('ids')
    new_id = ids.get(id,id)

    radio[id] = xbmcgui.Dialog().yesno(new_name,"Radio?")


@plugin.route('/channel_stream/<id>/<name>')
def channel_stream(id,name):
    #id = decode(id)

    #channels = plugin.get_storage('yo_channels')
    channel_stream_dialog(id,name)


@plugin.route('/zap_channel_stream/<id>')
def zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap2_channels')
    channel_stream_dialog(id,channels[id])


def channel_stream_dialog(id,name):
    #log(channel)
    #country,name,thumbnail = channel
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')
    #name = channel["name"]
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


@plugin.route('/guess_channel_stream/<id>/<name>')
def guess_channel_stream(id,name):
    #id = decode(id)

    #channels = plugin.get_storage('yo_channels')
    return guess_channel_stream_dialog(id,name)


@plugin.route('/guess_zap_channel_stream/<id>')
def guess_zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap2_channels')
    return guess_channel_stream_dialog(id,channels)


def guess_channel_stream_dialog(id,name):
    #country,name,thumbnail = channel

    streams = plugin.get_storage('streams')
    m3us = plugin.get_storage('subscribe_m3us')
    m3u_contents = plugin.get_storage('m3u_contents', TTL=60)
    names = plugin.get_storage('names')
    #name = channels[id]
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
        #log((addon,folder,paths))
        #addon_label = paths["plugin://"+addon]
        addon_label = xbmcaddon.Addon(addon).getAddonInfo('name')
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
                other.append(("other","[COLOR blue]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))

    for url in m3us:
        filename = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + urllib.parse.quote(m3us[url]))
        if filename in m3u_contents:
            data = json.loads(m3u_contents[filename])
        else:
            success = xbmcvfs.copy(url,filename)
            if success:
                fu = xbmcvfs.File(filename,"r")
                data = fu.read()
                m3u_contents[filename] = json.dumps(data)
            else:
                continue

        channels = re.findall('#EXTINF:(.*?)(?:\r\n|\r|\n)(.*?)(?:\r\n|\r|\n|$)', data.decode('utf-8'), flags=(re.I | re.DOTALL))
        for channel in channels:
            label = channel[0].rsplit(',', 1)[-1]
            file = channel[1]
            new_name_match = re.sub(" hd$",'',new_name.lower())
            addon = "m3u"
            addon_label = m3us[url]
            folder = url
            folder_label = addon_label
            if new_name_match == label.lower():
                exact.append(("exact","[COLOR yellow]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))
            elif new_name_match in label.lower():
                partial.append(("partial","[COLOR orange]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))
            else:
                other.append(("other","[COLOR blue]"+label+"[/COLOR]",addon,addon_label,folder,folder_label,file))


    all = sorted(exact,key=lambda k: k[1]) + sorted(partial,key=lambda k: k[1]) + sorted(other,key=lambda k: k[1])
    labels = ["%s %s" % (x[1],x[3]) for x in all]

    index = xbmcgui.Dialog().select("Stream: %s [%s]" % (new_name,new_id), labels )
    if index == -1:
        return True
    (type,label,addon,addon_label,folder,folder_label,file) = all[index]
    streams[id] = file


@plugin.route('/guess_missing_streams')
def guess_missing_streams():
    guess_streams_function(missing=True)


@plugin.route('/guess_streams')
def guess_streams():
    guess_streams_function()


def guess_streams_function(missing=False):
    channels = plugin.get_storage('channels')
    zap_channels = plugin.get_storage('zap2_channels')
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')

    all_channels = dict(list(channels.items()))
    all_channels.update(dict(list(zap_channels.items())))

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
            if not (streams.get(id) and missing):
                if guess_zap_channel_stream(id):
                    return
        if id in channels:
            if not (streams.get(id) and missing):
                if guess_channel_stream(id):
                    return


@plugin.route('/paste_channel_stream/<id>')
def paste_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('yo_channels')
    paste_channel_stream_dialog(id,channels)


@plugin.route('/paste_zap_channel_stream/<id>')
def paste_zap_channel_stream(id):
    id = decode(id)

    channels = plugin.get_storage('zap2_channels')
    paste_channel_stream_dialog(id,channels)


def paste_channel_stream_dialog(id,channels):
    streams = plugin.get_storage('streams')
    names = plugin.get_storage('names')
    country,name,thumbnail = channels[id]
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

    channels = plugin.get_storage('zap2_channels')
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

    zap_channels = plugin.get_storage('zap2_channels')
    names = plugin.get_storage('names')
    name = zap_channels[id]
    new_name = names.get(id,name)

    new_name = xbmcgui.Dialog().input(name,new_name)
    if new_name:
        names[id] = new_name
    elif id in names:
        del names[id]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_zap_channel/<name>/<id>/<country>/<thumbnail>')
def add_zap_channel(name,id,country,thumbnail):
    #name = name.decode("utf")
    #id = decode(id)

    channels = plugin.get_storage('zap2_channels')
    channels[id] = (name,id,country,thumbnail)

    #add_json_channel(id)
    #xbmc.executebuiltin('Container.Refresh')


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
    if '\\' in url:
        url = url.replace('\\','/')

    filename = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.xmltv.meld/temp/" + url.rsplit('?',1)[0].rsplit('/',1)[-1])

    with open(filename,'wb') as f:
        if url.startswith('http') or url.startswith('ftp'):
            data = requests.get(url).content
            f.write(data)
        else:
            f.write(xbmcvfs.File(url).read())

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
                add_channel(url=url,description=description.encode("utf8"),name=name.encode("utf8"), id=id.encode("utf8"),thumbnail=icon)
            if remove_all == True:
                delete_channel(id.encode("utf8"))

            context_items = []
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_channel',name=name.encode("utf8"), id=id.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8")))))
            #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8")))))

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
            context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=name.encode("utf8"), url=url))))
            label = name
        else:
            context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % name
        context_items.append(("[COLOR yellow]Remove xmltv url[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_custom_xmltv, url=url))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',url=url.encode("utf8"),description=name.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels, url=url.encode("utf8"),description=name.encode("utf8")))))

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
    sources = requests.get("http://rytecepg.epgspot.com/epg_data/rytec.King.sources.xml").content.decode('utf-8')

    urls = re.findall('<source.*?channels="(.*?)">.*?<description>(.*?)</description>.*?<url>(.*?)<',sources,flags=(re.I|re.DOTALL))

    items = []
    #xmltv = plugin.get_storage('xmltv')
    for channels,description,url in sorted(urls,key=lambda x: x[1]):

        context_items = []
        #log(url)
        if url not in xml_urls:
            #context_items.append(("[COLOR yellow]Subscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_xmltv, name=description, url=url))))
            label = description
        else:
            #context_items.append(("[COLOR yellow]Unsubscribe[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_xmltv, url=url))))
            label = "[COLOR yellow]%s[/COLOR]" % description
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_channels',description=description.encode("utf8"),url=url.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_channels,description=description.encode("utf8"), url=url.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('select_channels',url=url,description=description.encode("utf8")),
            'thumbnail':get_icon_path('tv'),
            'context_menu': context_items,
        })

    return items





@plugin.route('/koditvepg_xmltv')
def koditvepg_xmltv():

    urls = {'http://epg.koditvepg2.com/AT/guide.xml.gz': 'Austria', 'http://epg.koditvepg2.com/PL/guide.xml.gz': 'Poland', 'http://epg.koditvepg2.com/TR/guide.xml.gz': 'Turkey', 'http://epg.koditvepg2.com/IN/guide.xml.gz': 'India', 'http://epg.koditvepg2.com/FI/guide.xml.gz': 'Finland', 'http://epg.koditvepg2.com/SK/guide.xml.gz': 'Slovakia', 'http://epg.koditvepg2.com/CN/guide.xml.gz': 'China', 'http://epg.koditvepg2.com/NL/guide.xml.gz': 'Netherlands', 'http://epg.koditvepg2.com/GE/guide.xml.gz': 'Georgia', 'http://epg.koditvepg2.com/LU/guide.xml.gz': 'Luxembourg', 'http://epg.koditvepg2.com/SE/guide.xml.gz': 'Sweden', 'http://epg.koditvepg2.com/RU/guide.xml.gz': 'Russia', 'http://epg.koditvepg2.com/AU/guide.xml.gz': 'Australia', 'http://epg.koditvepg2.com/IS/guide.xml.gz': 'Iceland', 'http://epg.koditvepg2.com/AR/guide.xml.gz': 'Argentina', 'http://epg.koditvepg2.com/GB/guide.xml.gz': 'United Kingdom', 'http://epg.koditvepg2.com/RO/guide.xml.gz': 'Romania', 'http://epg.koditvepg2.com/ME/guide.xml.gz': 'Montenegro', 'http://epg.koditvepg2.com/NZ/guide.xml.gz': 'New Zealand', 'http://epg.koditvepg2.com/DE/guide.xml.gz': 'Germany', 'http://epg.koditvepg2.com/DO/guide.xml.gz': 'Dominican Rep.', 'http://epg.koditvepg2.com/BR/guide.xml.gz': 'Brazil', 'http://epg.koditvepg2.com/TH/guide.xml.gz': 'Thailand', 'http://epg.koditvepg2.com/DK/guide.xml.gz': 'Denmark', 'http://epg.koditvepg2.com/PH/guide.xml.gz': 'Philippines', 'http://epg.koditvepg2.com/AL/guide.xml.gz': 'Albania', 'http://epg.koditvepg2.com/PR/guide.xml.gz': 'Puerto Rico', 'http://epg.koditvepg2.com/RS/guide.xml.gz': 'Serbia', 'http://epg.koditvepg2.com/GR/guide.xml.gz': 'Greece', 'http://epg.koditvepg2.com/PA/guide.xml.gz': 'Panama', 'http://epg.koditvepg2.com/IE/guide.xml.gz': 'Ireland', 'http://epg.koditvepg2.com/TW/guide.xml.gz': 'Taiwan', 'http://epg.koditvepg2.com/JP/guide.xml.gz': 'Japan', 'http://epg.koditvepg2.com/MX/guide.xml.gz': 'Mexico', 'http://epg.koditvepg2.com/FR/guide.xml.gz': 'France', 'http://epg.koditvepg2.com/AE/guide.xml.gz': 'United Arab Emirates', 'http://epg.koditvepg2.com/MK/guide.xml.gz': 'Macedonia', 'http://epg.koditvepg2.com/HU/guide.xml.gz': 'Hungary', 'http://epg.koditvepg2.com/IL/guide.xml.gz': 'Israel', 'http://epg.koditvepg2.com/SA/guide.xml.gz': 'Saudi Arabia', 'http://epg.koditvepg2.com/UA/guide.xml.gz': 'Ukraine', 'http://epg.koditvepg2.com/PK/guide.xml.gz': 'Pakistan', 'http://epg.koditvepg2.com/LT/guide.xml.gz': 'Lithuania', 'http://epg.koditvepg2.com/KZ/guide.xml.gz': 'Kazakhstan', 'http://epg.koditvepg2.com/LV/guide.xml.gz': 'Latvia', 'http://epg.koditvepg2.com/BE/guide.xml.gz': 'Belgium', 'http://epg.koditvepg2.com/PT/guide.xml.gz': 'Portugal', 'http://epg.koditvepg2.com/CA/guide.xml.gz': 'Canada', 'http://epg.koditvepg2.com/VN/guide.xml.gz': 'Vietnam', 'http://epg.koditvepg2.com/HR/guide.xml.gz': 'Croatia', 'http://epg.koditvepg2.com/ES/guide.xml.gz': 'Spain', 'http://epg.koditvepg2.com/CZ/guide.xml.gz': 'Czech Rep.', 'http://epg.koditvepg2.com/EG/guide.xml.gz': 'Egypt', 'http://epg.koditvepg2.com/BG/guide.xml.gz': 'Bulgaria', 'http://epg.koditvepg2.com/CO/guide.xml.gz': 'Colombia', 'http://epg.koditvepg2.com/US/guide.xml.gz': 'United States', 'http://epg.koditvepg2.com/NO/guide.xml.gz': 'Norway', 'http://epg.koditvepg2.com/BA/guide.xml.gz': 'Bosnia and Herz.', 'http://epg.koditvepg2.com/CH/guide.xml.gz': 'Switzerland', 'http://epg.koditvepg2.com/IT/guide.xml.gz': 'Italy', 'http://epg.koditvepg2.com/SI/guide.xml.gz': 'Slovenia', 'http://epg.koditvepg2.com/XK/guide.xml.gz': 'Kosovo'}

    items = []
    xmltv = plugin.get_storage('xmltv')
    for url,description in urls.items():

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
    #data = xbmcvfs.File(url,'r').read()
    data = requests.get(url).content
    j = json.loads(data)
    channels = j.get('channels')

    items = []
    zap_channels = plugin.get_storage('zap2_channels')


    for channel in channels:
        name = channel.get('callSign')
        id = channel.get('id')
        icon = "http:" + channel.get('thumbnail').replace('?w=55','')

        if add_all == True:
            add_zap_channel(name.encode("utf8"), id.encode("utf8"),country=country,thumbnail=icon)
        if remove_all == True:
            delete_zap_channel(id.encode("utf8"))

        context_items = []
        context_items.append(("[COLOR yellow]Remove channel[/COLOR]", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_zap_channel, id=id.encode("utf8")))))
        #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_all_zap_channels',country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))
        #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove all channels", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_all_zap_channels, country=country, zipcode=zipcode, device=device, lineup=lineup, headend=headend))))

        if id in zap_channels:
            label = "[COLOR yellow]%s[/COLOR]" % name
            path = plugin.url_for(delete_zap_channel, id=id.encode("utf8"))
        else:
            label = name
            path = plugin.url_for('add_zap_channel',name=name.encode("utf8"), id=id.encode("utf8"),country=country,thumbnail=icon)

        icons[id] = icon

        items.append(
        {
            'label': label,
            'path': path, #plugin.url_for('add_zap_channel',name=name.encode("utf8"), id=id.encode("utf8")),
            'thumbnail':icon,
            'context_menu': context_items,
        })

    return items


@plugin.route('/zap')
def zap():
    items = []

    for i in ["1","2"]:
        for label, country in [("Canada","CAN"), ("USA","USA")]:

            context_items = []

            items.append(
            {
                'label': "%s %s" % (label,i),
                'path': plugin.url_for('zap_country',country=country,i=i),
                'thumbnail':get_icon_path('tv'),
                'context_menu': context_items,
            })

    return items


@plugin.route('/zap_country/<country>/<i>')
def zap_country(country,i):
    zaps = plugin.get_storage('zaps')

    if i == "1":
        i = ""

    zipcode = plugin.get_setting('zap.' + country.lower() + '.zipcode'+i)

    url = 'https://tvlistings.gracenote.com/gapzap_webapi/api/Providers/getPostalCodeProviders/' + country + '/' + zipcode + '/gapzap/en'
    #log(url)
    #sources = xbmcvfs.File(url,"r").read()
    sources = requests.get(url).content

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
            context_items.append(("[COLOR yellow]%s[/COLOR]" %"Add zap", 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_zap, name=name.encode("utf8"), url=url))))
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
    order = plugin.get_storage('order')

    all_channels = Yo().all_channels()

    new_order = []
    for channel in sorted(all_channels, key = lambda k: (k["provider"],k["country"],k["name"])):
        cid = channel["id"]
        new_order.append(cid)

    order.clear()
    for i,cid in enumerate(new_order):
        order[cid] = i


@plugin.route('/move_channel/<id>')
def move_channel(id):
    order = plugin.get_storage('order')

    all_channels = Yo().all_channels() + xml_all_channels() + zap_all_channels()

    channels = []
    name = ""
    new_order = []
    for channel in sorted(all_channels, key = lambda k: order.get(k["id"],-1)):
        label = "%d - %s - [%s] - %s" % (order.get(channel["id"],-1),channel["name"],channel["provider"],channel["country"])
        cid = channel["id"]
        thumbnail = channel["thumbnail"]
        channels.append((cid,label))
        if cid == id:
            name = label
        new_order.append(cid)

    labels = [c[1] for c in channels]

    index = xbmcgui.Dialog().select('%s: Move After?' % name, labels)
    if index == -1:
        return

    oldindex = new_order.index(id)
    new_order.insert(index+1, new_order.pop(oldindex))
    order.clear()
    for i,cid in enumerate(new_order):
        order[cid] = i


def zap_all_channels():
    channels = plugin.get_storage('zap2_channels')
    all = []
    for id,(name,id,country,thumbnail) in list(channels.items()):
        all.append({
            "id": id,
            "name": name,
            "thumbnail": thumbnail,
            "provider": "zap",
            "country": country,
        })
    return all

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

    all_channels = Yo().all_channels() + xml_all_channels() + zap_all_channels()

    items = []

    for channel in sorted(all_channels, key = lambda k: order.get(k["id"],-1)):
        label = "%d - %s - [%s] - %s" % (order.get(channel["id"],-1),names.get(channel["id"],channel["name"]),channel["provider"],channel["country"])
        id = channel["id"]
        name = channel["name"]
        thumbnail = channel["thumbnail"]
        #log(channel)
        context_items = []
        #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Remove Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_channel, id=id.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Change Channel Id", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel_id, id=id.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Rename Channel", 'XBMC.RunPlugin(%s)' % (plugin.url_for(rename_channel, id=id.encode("utf8"), name=name.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Channel Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(channel_stream, id=id.encode("utf8"), name=name.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Guess Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(guess_channel_stream, id=id.encode("utf8"), name=name.encode("utf8")))))
        context_items.append(("[COLOR yellow]%s[/COLOR]" %"Paste Stream", 'XBMC.RunPlugin(%s)' % (plugin.url_for(paste_channel_stream, id=id.encode("utf8")))))
        #context_items.append(("[COLOR yellow]%s[/COLOR]" %"Radio", 'XBMC.RunPlugin(%s)' % (plugin.url_for(radio_stream, id=id.encode("utf8")))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('move_channel',id=id.encode("utf8")),
            'thumbnail': thumbnail, #icons.get(id, get_icon_path('tv')),
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
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Dummy Channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_dummy_channels, id=id, path=folder_path))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folders_paths',id=id, path=folder_path),
            'thumbnail': get_icon_path('tv'),
            'context_menu': context_items,
        })

    for url in sorted(links):
        label = links[url]
        thumbnail = thumbnails[url]
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Dummy Channel', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_dummy_channel, url=url, label=label.encode("utf8")))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Dummy Channel', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_dummy_channel, url=url))))
        items.append(
        {
            'label': label,
            'path': url,
            'thumbnail': thumbnail,
            'context_menu': context_items,
            'is_playable': True,
            'info_type': 'Video',
            'info':{"mediatype": "movie", "title": label}
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
        try: response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail","enabled"])
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
        if addon["enabled"] != True:
            continue
        label = remove_formatting(addon['name'])
        id = addon['addonid']
        path = "plugin://%s/" % id
        paths[path] = label
        context_items = []
        if id in ids:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Dummy Channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_dummy_channels, id=id, path=path))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folders_paths',id=id, path=path),
            'thumbnail': get_icon_path('tv'),
            'context_menu': context_items,
        })
    return items


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
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove xmltv', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_xmltv'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_xmltv_channels'))))
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
    items.append(
    {
        'label': "Zap",
        'path': plugin.url_for('zap'),
        'thumbnail':get_icon_path('tv'),
    })

    items.append(
    {
        'label': "yo.tv",
        'path': plugin.url_for('yo'),
        'thumbnail':get_icon_path('tv'),
    })

    context_items = []
    #context_items.append(("[COLOR yellow]%s[/COLOR]" %'Sort Channels', 'XBMC.RunPlugin(%s)' % (plugin.url_for('sort_channels'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Guess All Streams', 'XBMC.RunPlugin(%s)' % (plugin.url_for('guess_streams'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Guess Missing Streams', 'XBMC.RunPlugin(%s)' % (plugin.url_for('guess_missing_streams'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Merge m3u', 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_merge_m3u'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove m3u', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_merge_m3u'))))
    items.append(
    {
        'label': 'Channels',
        'path': plugin.url_for('channels'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })

    context_items = []
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_folders'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Subscribe m3u', 'XBMC.RunPlugin(%s)' % (plugin.url_for('add_subscribe_m3u'))))
    context_items.append(("[COLOR yellow]%s[/COLOR]" %'Remove m3u', 'XBMC.RunPlugin(%s)' % (plugin.url_for('remove_subscribe_m3u'))))
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

    context_items = []
    if xbmc.getCondVisibility('system.platform.android'):
        context_items.append(("[COLOR yellow]%s[/COLOR]" %'Delete busybox', 'XBMC.RunPlugin(%s)' % (plugin.url_for('delete_busybox'))))
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
