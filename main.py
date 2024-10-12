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
Create the FASTAPI App, Set the Jinja2 Templates directory

'''
app = FastAPI()
templates = Jinja2Templates(directory='./templates')



'''
@Brief - 
Root Directory. Main Homepage. Holds the links for traversing around the site.

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/')
def form_post(request: Request):
    
    authLink = querySpotify.generateAuthLink()    
    return templates.TemplateResponse('index.html', context={'request': request, 'authLink' : authLink})


'''
@Brief - This page has information about CV-Computer Science

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/compsci')
def form_post(request: Request):

    return templates.TemplateResponse('compsci.html', context={'request': request})

'''
@Brief - This page has information about CV-Mathematics

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/math')
def form_post(request: Request):

    return templates.TemplateResponse('math.html', context={'request': request})


'''
@Brief - This page has information about CV-Physics

@Params[in] -
request - HTTP request send by user 
'''
@app.get('/physics')
def form_post(request: Request):

    return templates.TemplateResponse('physics.html', context={'request': request})


#Return a file
# @app.get("/currentSong/{user}")
# async def main(user : str):
        
#     # return f'{image} has been searched'
#     print("Grabbing Current Song for: {}".format(user) )
#     return FileResponse('./images/' + image)



@app.get('/scripts/{script}')
def get_script(script : str):
    
    return FileResponse('./scripts/' + script)

@app.get('/images/{image}')
def get_image(image : str):

    return FileResponse('./images/' + image)

@app.get('/css/{css}')
def get_css(css : str):

    return FileResponse('./css/' + css)

@app.get('/html/{html}')
def get_css(html : str):

    return FileResponse('./html/' + html)

@app.get('/projects/{subject}/{homeproj}/{paper}')
def get_css(subject : str, homeproj : str, paper: str):

    #media_type
    
    path = './projects/'  + subject + '/' + homeproj + '/' + paper
    
    # print(path)
    
    
    headers = {"Content-Disposition": "inline; " + "filename=" + paper}
    
    response = FileResponse(path, media_type="application/pdf", headers=headers) 


    return response


@app.get('/files/{file}')
def get_css(file : str):

    #media_type
    
    path = './files/'  + file
    
    # print(path)
    
    
    headers = {"Content-Disposition": "inline; " + "filename=" + file}
    
    response = FileResponse(path, media_type="application/pdf", headers=headers) 


    return response