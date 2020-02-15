import sys
import time
import urllib
import demjson




def getConfig(line):
    brackets = 0
    start = line.find("ytplayer.config")
    start = line.find( '{' , start ) 
    for i in range(start, len(line) ):
        c = line[i]
        if c == '{': brackets += 1
        if c == '}': 
            brackets -= 1
            if ( brackets == 0 ) :
                return line[start:i+1]
    return ""


def getCodec(config):
    #Format is 'mimeType': u'video/mp4; codecs="avc1.42001E, mp4a.40.2"'
    return config["mimeType"][config["mimeType"].find('codecs="') + len('codecs="'):-1]

def getMime(config):
    #Format is 'mimeType': u'video/mp4; codecs="avc1.42001E, mp4a.40.2"'
    return config["mimeType"][0: config["mimeType"].find(";")]

def getItag(config):
    return config["itag"]

def getContentLength(config):
    return config["contentLength"]

def getFPS(config):
    return config["fps"]

def getAudioSampleRate(config):
    return config["audioSampleRate"]

def getHeight(config):
    return config["height"]

def getWidth(config):
    return config["width"]

def getDuration(config):
    return int(int(config["approxDurationMs"])/1000)

def getInitRange(config):
    return str(config["initRange"]["start"])+"-"+str(config["initRange"]["end"])


def getIndexRange(config):
    return str(config["indexRange"]["start"])+"-"+str(config["indexRange"]["end"])


def getUnsignedURL(config):
    cipher = config["cipher"]
    cipher_splitted = cipher.split('&')
    sigParam = "sig"
    url = ""
    sig = ""
    for param in cipher_splitted:
        if ( "url=" in param ):
            url = param[4:]
        if ( "sp=" in param ):
            sigParam = param[3:]
        if ( "s=" in param ):
            sig = param[2:]

    if ( sigParam == "" or url == "" or sig == "" ):
        print "Couldn't Parse Cipher"
        exit(1)

    return (sigParam, url, sig)

def getPlayerJS(config):
    return "https://www.youtube.com/"+config["assets"]["js"]


def getDescrambledSignature(player_js, sig):
    player = urllib.urlopen(player_js) 
    sig = urllib.unquote(sig)
    if ( player.getcode() != 200 ):
        print "Player could not be fetched, exiting"
        exit(1)
    player = player.read()
    decoder = ""
    decodeRules = ""
    decoderClass = ""
    rulesDefinitions = ""

    for line in player.splitlines():
        if ( "(decodeURIComponent(" in line ):
            end = line.find( "(decodeURIComponent(" )
            start = line.rfind("=", 0, end)
            decoder = line[start + 1: end]

    if decoder == "" : 
        print "Couldn't find the decoder"
        exit(1)

    for line in player.splitlines():
        if decoder+"=" in line and "."+decoder+"=" not in line:
            decodeRules = line[ line.find(";") + 1 : line.find(";return") ]

    if decodeRules == "":
        print "Couldn't find decoding rules"
        exit(1)
    
    decoderClass = decodeRules[:decodeRules.find(".")]

    if decoderClass == "":
        print "Couldn't find decoder class"
        exit(1)
    
    tmpStart = player.find( decoderClass+"=" ) + len(decoderClass) + 2
    tmpEnd = player.find("}}", tmpStart) + 1

    rulesDefinitions = player[tmpStart:tmpEnd]

    rulesFunctions = rulesDefinitions.split() 

    functionDefinition = {}
    for func in rulesFunctions:
        name = func[: func.find(":")].strip()
        if "splice" in func:
            functionDefinition[name] = "splice"  
        elif "reverse" in func:
            functionDefinition[name] = "reverse"
        else:
            functionDefinition[name] = "swap"

    rules = decodeRules.split(";")

    descrambledSig = sig
    for rule in rules:
        param = int ( rule[ rule.rfind(",") + 1 : rule.rfind(")") ] )
        functionName = rule[ rule.find(".") + 1 : rule.find("(") ] 

        if functionDefinition[functionName] == "splice" :
            descrambledSig = descrambledSig[ param % len(descrambledSig): ]
        elif functionDefinition[functionName] == "reverse" :
            descrambledSig = descrambledSig [::-1]
        elif functionDefinition[functionName] == "swap" :
            param = param % len(descrambledSig)
            descrambledSig = descrambledSig[ param ] + descrambledSig[ 1 : param ] + descrambledSig[0] + descrambledSig[ param + 1: ]

        else:
            print "Function " + functionName + " was not found"
            exit(1)
    
    return descrambledSig
        







url = ""
reso = -1

for i in range(1,len(sys.argv),2 ):
    if ( sys.argv[i] == "--url" ): 
        if ( i + 1 < len( sys.argv ) ):
            url = sys.argv[ i + 1 ]
        else : 
            print( "URL not found, exiting...")
            exit(1)
    if ( sys.argv[i] == '--res' ): 
        if ( i + 1 < len ( sys.argv ) ):
            reso = sys.argv[ i + 1 ]
        else :
            print ("Preffered resolution could not be used, using the default -1 option")

if url == "":
    print "No Url Specified, exiting..."
    exit(1)

webpage = urllib.urlopen(url)

if ( webpage.getcode() != 200 ):
    print ( "Webpage could not be read, exiting..." )
    exit(1)

page_source = webpage.read()
raw_config = ""
for line in page_source.splitlines():
    if "ytplayer.config" in line:
        raw_config = getConfig(line)
        if ( raw_config != "" ) :
            break

if raw_config == "":
    print "YT Config Can't be read, exiting..."
    exit(1)


config = demjson.decode(raw_config)

player_js = getPlayerJS(config)

config = demjson.decode(config["args"]["player_response"])
config = config["streamingData"]

best_default_config = ""
best_default_height = -1
for def_config in config["formats"]:
    if getHeight( def_config ) > best_default_height and ( getHeight(def_config) < reso or reso == -1 ):
        best_default_height = getHeight(def_config) 
        best_default_config = def_config

def_sigParam, def_url, def_sig = getUnsignedURL( best_default_config )
def_descrambled_sig = getDescrambledSignature(player_js,def_sig)

print "To use a default stream, use the following link: "
print urllib.unquote(def_url+'&'+def_sigParam+"="+def_descrambled_sig)

best_height = -1
best_vid_conf = ""
best_aud_conf = ""

for conf in config["adaptiveFormats"]:
    if "video" in getMime(conf):
        height = getHeight(conf)
        if height > best_default_height and height > best_height and ( height < reso or reso == -1 ):
            best_height = height
            best_vid_conf = conf

if best_vid_conf == "" :
    print "The default format is the best resolution available, please use the default format"
    exit(1)

best_format = ""
if "mp4" in getMime(best_vid_conf):
    best_format = "mp4"
else: 
    best_format = "webm"

for conf in config["adaptiveFormats"]:
    if "audio" in getMime(conf):
        if best_format in getMime(conf):
            best_aud_conf = conf
            break

if best_aud_conf == "" :
    for conf in config["adaptiveFormats"]:
        if "audio" in getMime(conf):
            best_aud_conf = conf
            break
    if best_aud_conf == "":
        print "Couldn't find an audio file, please use the default version"
        exit(1)
vid_id = ""
if "v=" in url:
    vid_id = url[ url.find("v=")+2: ]
else:
    vid_id = url[ url.find("/"): ]

vid_sigParam, vid_url, vid_sig = getUnsignedURL(best_vid_conf)
vid_descrambled_sig = getDescrambledSignature(player_js, vid_sig)
aud_sigParam, aud_url, aud_sig = getUnsignedURL(best_aud_conf)
aud_descrambled_sig = getDescrambledSignature(player_js, aud_sig)

vid_dl_url = urllib.unquote( vid_url+"&"+vid_sigParam+"="+vid_descrambled_sig ).replace("&","&amp;")
aud_dl_url = urllib.unquote( aud_url+"&"+aud_sigParam+"="+aud_descrambled_sig ).replace("&","&amp;")


file_name = "/tmp/" + vid_id + "_" + str(time.time())+".mpd"

output = open(file_name, "w+")
output.write('''<?xml version="1.0" encoding="UTF-8"?>
<MPD
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xmlns="urn:mpeg:DASH:schema:MPD:2011"
	xmlns:yt="http://youtube.com/yt/2012/10/10" xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd" bufferingGoal="PT90S" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" mediaPresentationDuration="PT'''+str(getDuration(best_vid_conf))+'''S">
<Period>
	<AdaptationSet mimeType="'''+getMime(best_aud_conf)+'''" subsegmentAlignment="true">
		<Role schemeIdUri="urn:mpeg:DASH:role:2011" value="main"/>
		<Representation id="'''+str(getItag(best_aud_conf))+'''" codecs="'''+getCodec(best_aud_conf)+'''" audioSamplingRate="'''+str(getAudioSampleRate(best_aud_conf))+'''" startWithSAP="1" >
			<AudioChannelConfiguration schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011" value="2"/>
			<BaseURL yt:contentLength="'''+str(getContentLength(best_aud_conf))+'''">'''+aud_dl_url+'''</BaseURL>
				<SegmentBase indexRange="'''+getIndexRange(best_aud_conf)+'''" indexRangeExact="true">
					<Initialization range="'''+getInitRange(best_aud_conf)+'''" />
				</SegmentBase>
			</Representation>
		</AdaptationSet>
		<AdaptationSet mimeType="'''+getMime(best_vid_conf)+'''" subsegmentAlignment="true">
			<Role schemeIdUri="urn:mpeg:DASH:role:2011" value="main"/>
			<Representation id="'''+str(getItag(best_vid_conf))+'''" width="'''+str(getWidth(best_vid_conf))+'''" height="'''+str(getHeight(best_vid_conf))+'''" frameRate="'''+str(getFPS(best_vid_conf))+'''" codecs="'''+getCodec(best_vid_conf)+'''">
				<BaseURL yt:contentLength="'''+str(getContentLength(best_vid_conf))+'''">'''+vid_dl_url+'''</BaseURL>
				<SegmentBase indexRange="'''+getIndexRange(best_vid_conf)+'''" indexRangeExact="true">
					<Initialization range="'''+getInitRange(best_vid_conf)+'''" />
				</SegmentBase>
			</Representation>
		</AdaptationSet>
	</Period>
</MPD>''')
output.close()
print "Generated MPD file could be found here : "
print file_name
