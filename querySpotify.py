import threading
from threading import Lock
from time import sleep
import queue
import time
import datetime as dt
import queue
import json
import requests
import base64
import passwords
import os



'''
@Brief -
REQUEST_TOKEN_URL - The url to request an access token
CURRENTLY_PLAYING_URL - The url to request the currently playing song
AUTHORIZE_URL - The url to authorize spotify (Needed for authorization link)
REDIRECT_URI - The url to redirect to after the code digest is recieved from the auth link
GET_CURRENT_USER_PROFILE_URL - The url to grab the current user profile information
'''


#NO MAGIC CONSTANTS
REQUEST_TOKEN_URL = 'https://accounts.spotify.com/api/token'
CURRENTLY_PLAYING_URL = 'https://api.spotify.com/v1/me/player/currently-playing'
AUTHORIZE_URL = 'https://accounts.spotify.com/en/authorize'
REDIRECT_URI = 'http://localhost:8000/auth-redirect'
# REDIRECT_URI = 'http://127.0.0.1:8000/auth-redirect'
# REDIRECT_URI = 'http://192.168.7.23:8000/auth-redirect'
GET_CURRENT_USER_PROFILE_URL = "https://api.spotify.com/v1/me"


#File Names

DATA_FILE = 'data.json'
ENDPOINT_REFRESH_TIME = 5
DRIFT_BUFFER_MS = 8000
SKIP_THRESH = 30000
#Response Status Codes

STATUS_NO_CONNECTION = -1
STATUS_OK = 200
STATUS_CREATED = 201
STATUS_ACCEPTED = 202
STATUS_NO_CONTENT = 204
STATUS_NOT_MODIFIED = 304
STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_TOO_MANY_REQUESTS = 429
STATUS_INTERNAL_SERVER_ERROR = 500
STATUS_BAD_GATEWAY = 502
STATUS_SERVICE_UNAVAILABLE = 503

#IF THERE ARE BROKEN PERMISSIONS, CAN TOGGLE ON AND OFF (THINK SPOTIFY UPDATE?)
#PERMISSIONS DICT

'''
@Brief - 
https://developer.spotify.com/documentation/web-api/concepts/scopes
This link has the information for all the scopes, along with the web documentation of what permissions are needed for each type of query.

'''
   
PERMISSIONS = {'user-read-currently-playing' : True, 'user-read-playback-position' : True, 'user-read-recently-played' : True, 'user-read-playback-state' : True, 'user-read-recently-played' : True, 'playlist-read-private' : True, 'playlist-read-collaborative' : True, 'user-read-playback-position' : True, 'user-library-read' : True, 'user-read-email' : True, 'user-top-read' : True, 'user-follow-read' : True, 'user-read-private' : True}

'''
@Brief - Mailbox for working with multiple threads, as well as a FIFO queue for the current song information.

@Params -
self.refreshToken - Stores the refresh token for the user. Needed for the refresh token thread
self.accessToken - Stores the access token to allow for queries
self.userName - Stores the username for the queries
self.lock - Mutex lock for values in the Mailbox.
self.entries - A FIFO queue for the current song

pushEntry - pushes an entry onto the FIFO queue. The queue is already blocking.
popEntry - pop an entry off the FIFO queue. The queue is already blocking.
setRefreshToken - Set the refresh Token with mutex 
getRefreshToken - Get the refresh Token with mutex
setAccessToken - Set the access Token with mutex 
getAccessToken - Get the access Token with mutex
setUserName - Set the access Token with mutex 
getUserName - Get the access Token with mutex

'''
class Mailbox:
    def __init__(self):
        self.refreshToken = 'DEFAULT'
        self.accessToken = 'DEFAULT'
        self.userName = 'DEFAULT'
        self.lock = Lock()
        self.entries = queue.Queue()

    def pushEntry(self, Entry):
        self.entries.put(Entry)
            
    def popEntry(self):
        return self.entries.get()
    
    def setRefreshToken(self, refreshToken):
        with self.lock:
            self.refreshToken = refreshToken
            
    def getRefreshToken(self):
        with self.lock:
            refreshToken = self.refreshToken
        return refreshToken
    
    def setAccessToken(self, accessToken):
        with self.lock:
            self.accessToken = accessToken
            
    def getAccessToken(self):
        with self.lock:
            accessToken = self.accessToken
        return accessToken
    
    def setUserName(self, userName):
        with self.lock:
            self.userName = userName
            
    def getUserName(self):
        with self.lock:
            userName = self.userName
        return userName

 

 
    
'''
@Brief -

Opens a JSON file with a try-except block (The JSON errors get caught, instead of needing a mutex, the error is thrown and excepted)
Ultimately faster and easier than using a mutex. No known errors. Essentially a more robust wrapper.
 
@Params[in] - 
fileName - The file name to open.

@Params[out] - 
None if no file exists.


'''    
    
def openJsonFile(fileName):
    
    if os.path.exists(fileName):
    
        while True:
            try:
                f = open(fileName)
                fileContents = json.load(f)
                f.close()
                return fileContents
            except:
                print("Read Error")
    else:
        print("File Does not exist")
        return None
            

'''
@Brief -

Saves a JSON file with a try-except block (The JSON errors get caught, instead of needing a mutex, the error is thrown and excepted)
Ultimately faster and easier than using a mutex. No known errors. Essentially a more robust wrapper.
 
@Params[in] - 
fileName - The file name to open.
fileContents - The file contents to save. Expecting key-value dictionary

@Params[out] - 
None if no file exists.


'''
           
def saveJsonFile(fileName,fileContents):
    while True:
        try:
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(fileContents, f, ensure_ascii=True, indent=4)
            return 0
        except:
            print("Write File Error")

'''
@Brief - Gets the current song, essentially a wrapper for the currently playing song query
to create an entry to be saved in JSON format. Pushes it onto the mailbox FIFO queue. 
Keeps the returned JSON from the current song query, as well as a pared down version of the information.
The information that it saves to JSON is:
-TrackID
-Song Name
-Album Name
-Artist
-Approximate Time the Song began, with resolution of the query time. 
-Duration of the Song

 
@Params[in] - 
mailbox - Used for storing FIFO queue information, pushes the tuple entry for saving (see above) and the original JSON for the endpoint.


@Params[out] - None


'''
def getCurrentSong(mailbox):
    
    responseCode = 0

    REQUEST_CURRENT_SONG_HEADERS = {'Authorization' : 'Bearer {}'.format(mailbox.getAccessToken())}
    #If status unauthorized, need to re-auth token.
    try:
        res = requests.get(CURRENTLY_PLAYING_URL, headers=REQUEST_CURRENT_SONG_HEADERS)
        responseCode = res.status_code
    except:
        # print("Current Song Routine: No Connection")
        responseCode = STATUS_NO_CONNECTION
        
    if responseCode != STATUS_NO_CONNECTION:
        
        responseCode = res.status_code
    
    
    #Debug to see which response code to catch
    # print("Current Song Response: ", responseCode)
    
    #Chill on the requests if there are too many
    #Could be an issue, think about it
    if responseCode == STATUS_TOO_MANY_REQUESTS:
        sleep(180)
        
    if responseCode == STATUS_UNAUTHORIZED:
        #Need to Reauthorize
        print("Unauthorized - ", mailbox.getUserName())
        #Immediately reauth (one time use of the authorize loop)
        
        
        #Spawn a thread here instead
        # threadRefreshToken(mailbox,0)
        z = threading.Thread(target=threadRefreshToken, args=(mailbox,), daemon=True)
        z.start()
        
        return

        
        #In the event the refresh Token thread dies, make sure it is dead, then spawn another one here.
    if responseCode == STATUS_NO_CONNECTION:
        print("Current Song Routine: No Connection - ", mailbox.getUserName())
        return
    
    if responseCode == STATUS_NO_CONTENT:
        now = str(dt.datetime.now())
        print(now,": No Content - ", mailbox.getUserName())
        return
            


    
    # print(res.status_code)
    songID = (res.json()['item'])['id']
    songName = (res.json()['item'])['name']
    albumName = ((res.json()['item'])['album'])['name']
    artistName = ((((res.json()['item'])['album'])['artists'])[0])['name']
    duration = (res.json()['item'])['duration_ms']
    now = str(dt.datetime.now())
    
    date = now.split(" ")
    # calendarDay = date[0]
    timePlayed = date[1]
    
    newTupleEntry = [songID,songName,albumName,artistName,timePlayed,duration]
    
    
    entryRezzPair = [res.json(),newTupleEntry]
    
    mailbox.pushEntry(entryRezzPair)
    
    return

'''
@Brief - Manages creating and starting threads for grabbing current song. 
Each thread calls getCurrentSong, and pushes values onto the mailbox
FIFO queue. It creates threads at the rate of queryTime.
 
@Params[in] - 
mailbox - FIFO queue to be passed into currentSong threads.
queryTime - How fast each query thread is made and started.


@Params[out] - 
None

'''
def currentSongThreadManager(mailbox, queryTime):
    while(True):
        z = threading.Thread(target=getCurrentSong, args=(mailbox,), daemon=True)
        z.start()
        sleep(queryTime)


'''
@Brief - Refresh Token thread manager. Responsible for creating and starting refresh token threads. 

 
@Params[in] - 
mailbox - FIFO queue to hold the refresh token.
refreshTime - How frequent refreshToken scripts are called

@Params[out] - 
None

'''
def refreshTokenThreadManager(mailbox, refreshTime):
    while(True):
        z = threading.Thread(target=threadRefreshToken, args=(mailbox,), daemon=True)
        z.start()
        sleep(refreshTime)

def endpointThreadManager(endpointRefresh):
    while(True):
        
        listenEndpointThread = threading.Thread(target=createTotalListensEndpoint, args=(), daemon=True)
        listenEndpointThread.start()
        sleep(endpointRefresh)

'''
@Brief -
Creates a JSON for total listens
'''
def createTotalListensEndpoint():
    
    songData = openJsonFile(DATA_FILE)

    print("Creating JSON")
    
    if songData == None:
        return
    
    else:
        
        totalArtistListens = {}    
        
        keyArray = [*songData]
        
        skipped = False
        
        for i,key in enumerate(songData):
            
            item = (songData[key])['item']
            
            #Some songs appear twice...
            artists = (item['artists'])
            albumName = (item['album'])['name']
            songName = item['name']
            
            
            if i < len(keyArray) - 1:
                keyNum1 = keyArray[i]
                keyNum2 = keyArray[i+1]
            
            sd1 = songData[keyNum1]
            sd2 = songData[keyNum2]
            
            
            ts1 = sd1['timestamp']
            ts2 = sd2['timestamp']
            
            d1 = (sd1['item'])['duration_ms']
            
            # #Logic for Skips
            # #(ts1+d1+DRIFT_BUFFER_MS > ts2) and (ts2-ts1 > d1-DRIFT_BUFFER_MS)

            # print(ts2 - ts1, d1, (ts1+d1+DRIFT_BUFFER_MS > ts2) and (ts2-ts1 > d1-DRIFT_BUFFER_MS))


            # if((ts1+d1+DRIFT_BUFFER_MS > ts2) and (ts2-ts1 > d1-DRIFT_BUFFER_MS)):
            #     print("Not skipped")
            #     skipped = False
            # else:
            #     print("Skipped")
                

            # if (ts2-ts1 < SKIP_THRESH):
            #     print("skipped")
            #     skipped = True
            # else:
            #     print("not skipped")
            #     skipped = False
            
            

            
            
            
            
            #Grab Artist Names to iterate over
            artistNames = []
            for artist in artists:
                artistName = artist['name']
                artistNames.append(artistName)


            for artist in artistNames:
                if artist not in totalArtistListens:
                    #New Artist
                    totalArtistListens[artist] = {'listens' : 1, albumName : {'listens' : 1 , songName : 1}}
                else:
                    #Grab Artist Listens
                    artistListensAndAlbums = totalArtistListens[artist]
                    
                    
                    artistListensAndAlbums['listens'] +=1
                    if albumName not in artistListensAndAlbums:
                        #New Album
                        artistListensAndAlbums[albumName] = {'listens' : 1, songName : 1}
                    else:
                        
                        (artistListensAndAlbums[albumName])['listens'] += 1

                        albumListensAndSongs = artistListensAndAlbums[albumName]
                        
                        if songName not in albumListensAndSongs:
                            albumListensAndSongs[songName] = 1
                        else:
                            albumListensAndSongs[songName] +=1
                        
                            

                    
                    
                    # (totalArtistListens[artist])['listens'] +=1
                    # ((totalArtistListens[artist])[albumName])['listens'] +=1
                    # ((totalArtistListens[artist])[albumName])[songName] +=1
                
            
                
            
            # print(albumName,songName)
            # for artist in artists:
                
                # artistName = artist['name']
                
                # if artistName not in totalArtistListens:
                    # totalArtistListens[name] = {}
                    
                        
                    
                    
                    # print(totalArtistListens)
                
                # else:
                    # print("Hi")
                    # print((totalArtistListens[name])['listens'])
                    # (totalArtistListens[artistName])['listens'] += 1
                    # print((totalArtistListens[name])['listens'])
                
        # print(totalArtistListens)
        saveJsonFile('listens.json', totalArtistListens)
        return


'''
@Brief - creates and sets the accessToken for querying spotify's API

 
@Params[in] - 
code - code digest needed to generate a accessToken, refreshToken


@Params[out] - 
JSON of accessToken returned from query to site.


'''
def createAccessToken(code: str):
    auth_str = '{}:{}'.format(passwords.SPOTIFY_CLIENT_ID, passwords.SPOTIFY_CLIENT_SECRET)
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    REQUEST_TOKEN_HEADERS = {'Content-type': 'application/x-www-form-urlencoded', 'Authorization' : 'Basic {}'.format(b64_auth_str)}
    REQUEST_TOKEN_DATA_AUTH = {'grant_type' : 'authorization_code', 'code' : str(code), 'redirect_uri' : 'http://localhost:8000/auth-redirect'}
    
    res = requests.post(REQUEST_TOKEN_URL,headers=REQUEST_TOKEN_HEADERS, data=REQUEST_TOKEN_DATA_AUTH)

    return res.json()

'''
@Brief - Generates an Authentication link, that controls permissions granted for user. Permissions are at the top, PERMISSIONS.

 
@Params[in] - 
None

@Params[out] - 
Authentication Link to authenticate spotify permissions.

'''
def generateAuthLink():
    
    scope = ""
    
    for i,key in enumerate(PERMISSIONS):
        if (PERMISSIONS[key] and i == 0):
            scope += key
        if (PERMISSIONS[key]):
            scope += " " + key
    
    
    
    linkWithPermissions = AUTHORIZE_URL + '?client_id=' + passwords.SPOTIFY_CLIENT_ID + '&redirect_uri=' + REDIRECT_URI + '&response_type=code&scope=' + scope

    return linkWithPermissions

'''
@Brief - Grabs the current user profile

 
@Params[in] - 
token - access Token, needed for authorization


@Params[out] - 
res.json() returns the json for user profile.

'''
def getCurrentUserProfile(token):
    
    REQUEST_HEADERS = {'Authorization' : 'Bearer {}'.format(token)}
    
    res = requests.get(GET_CURRENT_USER_PROFILE_URL, headers=REQUEST_HEADERS)
    
    return res.json()

#To make it clean, make sure this one is also nice |-|-|-

#It's cleaner now! Yay!
'''
@Brief - 
Refreshes the refresh token and access token to keep it valid.
 
@Params[in] - 
mailbox - used to store the access token and refresh token so other threads can use it

@Params[out] - 
None

'''
def threadRefreshToken(mailbox):
    
    now = dt.datetime.now()
    print("Refreshing Token: {} - {}".format(now.time(), mailbox.getUserName())) 
    
    auth_str = '{}:{}'.format(passwords.SPOTIFY_CLIENT_ID, passwords.SPOTIFY_CLIENT_SECRET)
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    REQUEST_TOKEN_HEADERS = {'Content-type': 'application/x-www-form-urlencoded', 'Authorization' : 'Basic {}'.format(b64_auth_str)}
    REFRESH_TOKEN_DATA = {'grant_type' : 'refresh_token', 'refresh_token' : mailbox.getRefreshToken() , 'client_id' : passwords.SPOTIFY_CLIENT_ID}
    
    responseCode = 0
    while(responseCode != 200):
        try:
            res = requests.post(REQUEST_TOKEN_URL,headers=REQUEST_TOKEN_HEADERS, data=REFRESH_TOKEN_DATA)
            responseCode = res.status_code
            
        except:
            responseCode = STATUS_NO_CONNECTION
        
        if responseCode != STATUS_NO_CONNECTION:
            responseCode = res.status_code

        
        if responseCode == STATUS_TOO_MANY_REQUESTS:
            print("Refresh Token Routine: Too Many Requests - ", mailbox.getUserName())
            sleep(60)
        if responseCode == STATUS_NO_CONNECTION:
            print("Refresh Token Routine: Lost connection - ", mailbox.getUserName())
                
    mailbox.setAccessToken(res.json()['access_token'])

    return


def readSongData(mailbox, userContainer):
    
    prevSongID = '+'
    songID = '+'
    
    entryResPair = mailbox.popEntry()
    name = mailbox.getUserName()
    
    #Could run into a unicode error here
    
    # dataFileName = 'data-' + name + '.json'
    dataFileName = DATA_FILE
    
    userContainer.setCurrentSongRes(entryResPair[0])
    
    entry = entryResPair[1]
    
    # print(entry)
    now = str(dt.datetime.now())

    date = now.split(" ")
    calendarDay = date[0]
    timePlayed = date[1]
    
    songID = entry[0]
    
    if prevSongID != songID:
        #Song Changed to New song
        prevSongID = songID
        print("New Song - ", mailbox.userName)
        
        songData = openJsonFile(dataFileName)
            
        if songData == None:
            songData = {}
        
        try:
            songDays = songData[name]
        except:
            songData[name] = {}
            songDays = songData[name]
        
        
        #Make sure to check to see if the key exists (First entry of the day) + []
        try:
            songTuples = songDays[calendarDay]
        except:
            #Key did not exist, first entry of the day
            songDays[calendarDay] = []
            songTuples = songDays[calendarDay]
        
        
        songTuples.append(entry)
        
        saveJsonFile(fileName=dataFileName,fileContents=songData)
    
    else:
        #If the song is longer than when the last entry was (of the same name), (check with duration), update when the song is playing
        print("Same Song - ", mailbox.userName)
    
    
    
    return

def generateDataFile(mailbox, userContainer):
    
    #This is for the endpoint, sets the endpoint 
    entryResPair = mailbox.popEntry()
    userContainer.setCurrentSongRes(entryResPair[0])
    
    
    #===========================================#
    
    # print("Setting Data")
    entry = entryResPair[1]
    
    
    now = str(dt.datetime.now())
    # date = now.split(" ")
    # calendarDay = date[0]
    # timePlayed = date[1]
    
    # currentSongID = (entryResPair[1])[0]
    
    
    songData = openJsonFile(DATA_FILE)
    
    #No File yet. Upon Startup.
    if songData == None:
        songData = {}
        songData[now] = entryResPair[0]
        saveJsonFile(DATA_FILE, songData)
    else:

        #Turn keys into an arraylist
        arrayListDates = [*songData]
        mostRecentKey = arrayListDates[-1]
        mostRecentSong = songData[mostRecentKey]
        
        mostRecentID = (mostRecentSong['item'])['id']
        
        
        # print(mostRecentID)
        
        
        currentID = ((entryResPair[0])['item'])['id']
        # print(currentID)
        
        #Remember Current Progress can break and glitch to Max
        currentProgressMS = ((entryResPair[0])['progress_ms'])
        currentDurationMS = ((entryResPair[0])['item'])['duration_ms']
        uniqueTimestamp = (entryResPair[0])['timestamp']
        
        
        #Assume this to be the case, we hit it directly, correction later.

        
        #Save The song if it is not the same
        if currentID != mostRecentID:
            print("Saving Song... - ", mailbox.getUserName())
            songData[now] = entryResPair[0]
            saveJsonFile(DATA_FILE, songData)
            actualStart = uniqueTimestamp
            actualEnd = uniqueTimestamp + currentDurationMS
            
            
            
            #Assuming song was already at the end, in which case it will go to the next song.
            #Assuming a bug
            if currentProgressMS != currentDurationMS:
                #Assume we start the song as normal.
                
                
                #We correct actual start here.
                actualStart = uniqueTimestamp - currentProgressMS
                actualEnd = uniqueTimestamp + currentDurationMS
                
            
        
        #See if it's repeating
        else:
            
            #Assuming Maxed out bug, or hitting it directly at the end.
            if currentProgressMS == currentDurationMS:
                currentprogress = 0
            #What if you 
            
            print("Same Song")

    
    return

# def generateDataFile(mailbox, userContainer):
    
#     #This is for the endpoint, sets the endpoint 
#     entryResPair = mailbox.popEntry()
#     userContainer.setCurrentSongRes(entryResPair[0])
    
#     return


        
'''
@Brief - 
Main thread loop. Takes care of new music data. (Could move this to separate thread)
 
@Params[in] -  
userContainer - Stored userName, store refresh token

@Params[out] - 
None

'''   

def newSpotifyUserThread(userContainer):
    
    mailbox = Mailbox()
    
    mailbox.setUserName(userContainer.userName)
    mailbox.setRefreshToken(userContainer.refreshToken)
    queryTime = userContainer.queryTime
    
    refreshDaemon = threading.Thread(target=refreshTokenThreadManager,args=(mailbox, 900), daemon=True)
    currentSongDaemon = threading.Thread(target=currentSongThreadManager, args=(mailbox, queryTime), daemon=True)
    
    
    endpointThreads = threading.Thread(target=endpointThreadManager, args=(ENDPOINT_REFRESH_TIME,), daemon=True)
    
    
    
    refreshDaemon.start()
    currentSongDaemon.start()
    
    endpointThreads.start()
    
    prevSongID = '+'
    songID = '+'
    
    while(True):
        
        # readSongData(mailbox, userContainer)
        generateDataFile(mailbox, userContainer)
        # createTotalListensEndpoint()