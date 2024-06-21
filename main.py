from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder

import querySpotify

from threading import Lock
import threading
import json
import requests
import queue

'''
@Brief - 
USER_FILE = user.json
Lists the tokens of the user.

'''

USER_FILE = 'user.json'


'''
=====================================================================
@Brief - Starts a group of threads (3) that run constantly in the 
background and collect data about currently playing song

@Params[in] - 
userContainer - Holds information about the user, such as refreshToken, queryTime, and userName

@Params[out] - Returns a Daemon process & that can be stopped and started again if need be. (Allows for restarting a thread remotely)
 
=====================================================================
'''
def startUserAPIThread(userContainer):
    
    daemonProcess = threading.Thread(target=querySpotify.newSpotifyUserThread,args=(userContainer,), daemon=True)
    daemonProcess.start()
    return daemonProcess

'''
=====================================================================
@Brief - 
Creates user threads to run in the background and collect music data

@Params[in] - 
None

@Params[out] - 
UserDaemonList - List of Daemon Processes
=====================================================================
'''
def createUserThread():
    #List the the threads are stored in. 
    userDaemonList = []
    userInfoList = {}
    userThreadList = querySpotify.openJsonFile(USER_FILE)


    if userThreadList != None:
        for key in userThreadList:
            refreshToken = (userThreadList[key])['refreshToken']
            
            userInfoContainer = CurrentSongContainer()
            
            #Set The Username
            userInfoContainer.userName = key
            
            userInfoList[key] = (userInfoContainer)
            userInfoContainer.refreshToken = refreshToken

            userThread = startUserAPIThread(userContainer=userInfoContainer)
            # userThread = serverHelpers.startUserAPIThread(name='Rippy',queryTime=5, userContainer=userInfoContainer)

            userDaemonList.append(userThread)



    '''
    Thread List ** Need to make thread management page
    '''
    # print(len(userDaemonList))
    
    
    
    
    return userDaemonList,userInfoList

'''
=====================================================================
@Brief - Stores the Data needed to transfer information from the daemon threads to the main routine

@Params[in] - 
self.lock - Mutex Lock for accessing values. Un-used, but may be needed later on.
self.resEntry - Place to store the res.json() for serving to the page from the threads
self.refreshToken - Stores the refreshToken (may not be needed)
self.userName - Stores the name of the user
=====================================================================
'''
class CurrentSongContainer:
    def __init__(self):
        self.lock = Lock()
        self.resEntry = ''
        self.refreshToken = 'DEFAULT'
        self.userName = 'DEFAULT'
        self.queryTime = 5
    
    def getCurrenSongRes(self):
        
        return self.resEntry
    
    def setCurrentSongRes(self, Entry):
        with self.lock:
            self.resEntry = Entry
        
        return


'''
@Brief - 
Create the FASTAPI App, Set the Jinja2 Templates directory, and create user thread (for collecting music data) 
'''
app = FastAPI()
templates = Jinja2Templates(directory='./templates')
daemon_list, user_info_list = createUserThread()



'''
@Brief - 
Root Directory. Main Homepage. Holds the links for traversing around the site.

@Params[in] -
request - HTTP request send by user 
'''






'''
@Brief - 
Main Homepage for Spotify App. Holds the links for traversing around the site.

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/')
def form_post(request: Request):
    
    authLink = querySpotify.generateAuthLink()    
    return templates.TemplateResponse('index.html', context={'request': request, 'authLink' : authLink})


'''
@Brief - 
Main Homepage for Spotify App. Holds the links for traversing around the app.

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/spotify-api')
def form_post(request: Request):
    
    authLink = querySpotify.generateAuthLink()    
    return templates.TemplateResponse('spotifyAppLinks.html', context={'request': request, 'authLink' : authLink})



'''
@Brief - This page has information about the currently playing song

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/currentSong')
def form_post(request: Request):

    return templates.TemplateResponse('currentSongPage.html', context={'request': request})


'''
@Brief - This page is about webgl. Working/Playing around with this.

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/webgl')
def form_post(request: Request):

    return templates.TemplateResponse('webgl.html', context={'request': request})

# @app.get('/totalListens')
# def form_post(request: Request):

#     return templates.TemplateResponse('currentSongPage.html', context={'request': request})



'''
@Brief -
Auth-redirect page, needed to authorize Spotify account

@Params[in] -
request - HTTP request send by user 
code - Spotify code digest, needed to create authorization token

'''
@app.get('/auth-redirect')
def form_post(request: Request, code : str):
    
    #Queries spotify for the access token, returns a JSON from the code digest
    responseJSON = querySpotify.createAccessToken(code=code)
    
    #Grab the access tokens
    accessToken = responseJSON['access_token']
    refreshToken = responseJSON['refresh_token']
    
    #Create token dictionary
    tokens = {'accessToken'  : accessToken, 'refreshToken' : refreshToken}
    
    
    #Grabs the current user profile, needed for making the userlist key-value pair (username - tokens)
    userProfile = querySpotify.getCurrentUserProfile(accessToken)

    #Need error handling if not self user
    
    if type(userProfile) != dict:
        return f'FORBIDDEN'
    
    #Set the Username
    userID = userProfile['id']
    
    
    #Open userJSON, if new, will spawn new threads to collect music data
    userJSON = querySpotify.openJsonFile(fileName=USER_FILE)
    
    if userJSON == None:
        
        userJSON = {}
        userJSON[userID] = tokens
        
        querySpotify.saveJsonFile(fileName=USER_FILE,fileContents=userJSON)
    
    
        #Spawns a new thread for the user, so it works the first time without restart!
        print("Start a thread for the new user")
        daemon_list2, user_info_list2 = createUserThread()
        user_info_list[userID] = user_info_list2[userID]
    
    else:
        
        
        #See if the user is already a part of the userJSON
        if userID in userJSON:
            print("Threads Running")
        
        else:
            print("Start a thread for the new user")
            createUserThread()
            
        
        
        userJSON[userID] = tokens
        querySpotify.saveJsonFile(fileName=USER_FILE,fileContents=userJSON)
        
    
    
    # return tokens
    return templates.TemplateResponse('authPage.html', context={'request': request})

#Return a file
# @app.get("/currentSong/{user}")
# async def main(user : str):
        
#     # return f'{image} has been searched'
#     print("Grabbing Current Song for: {}".format(user) )
#     return FileResponse('./images/' + image)


'''
@Brief -
Current Song for User, endpoint. Contains JSON information of the currentsong

'''

#CHANGE THIS TO spotify-api/

@app.get("/spotify-api/currentSong")
def main():
        
    # print("Grabbing Current Song for: {}".format(user))
    
    userFile = querySpotify.openJsonFile(USER_FILE)
    
    #Endpoint returns no file if the user file does not exist
    if userFile == None:
        return f'NO FILE'
    
    
    for key in user_info_list:
    
        return user_info_list[key].getCurrenSongRes()
    
@app.get('/spotify-api/{endpoint}')
def book_class(endpoint : str):
    
    if endpoint == 'listens':
        return FileResponse('listens.json')
        



    return FileResponse('./data.json')

@app.get('/scripts/{script}')
def book_class(script : str):
    
    

    return FileResponse('./scripts/' + script)

@app.get('/images/{image}')
def book_class(image : str):
    
    

    return FileResponse('./images/' + image)