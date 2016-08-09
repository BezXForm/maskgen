import numpy as np
import cv2
from subprocess import call,Popen, PIPE
import os
import json

def otsu(hist):
  total = sum(hist)
  sumB = 0
  wB = 0
  maximum = 0.0
  sum1 = np.dot( np.asarray(range(256)), hist)
  for ii in range(256):
    wB = wB + hist[ii]
    if wB == 0:
        continue
    wF = total - wB;
    if wF == 0:
        break
    sumB = sumB +  ii * hist[ii]
    mB = sumB / wB
    mF = (sum1 - sumB) / wF;
    between = wB * wF * (mB - mF) * (mB - mF);
    if between >= maximum:
        level = ii
        maximum = between
  return level

#def findRange(hist,perc):
#  maxvalue = hist[0]
#  maxpos = 0
#  maxdiff = 0
#  lastv = hist[0]
#  for i in range(1,256):
#    diff = abs(hist[i]-lastv)
#    if (diff > maxdiff):
#      maxdiff = diff
#    if hist[i] > maxvalue:
#      maxvalue = hist[i]
#      maxpos = i
#  i = maxpos-1
#  lastv = maxvalue
#  while i>0:
#    diff = abs(hist[i]-lastv)
#    if diff <= maxdiff:
#      break
#    lastv=hist[i]
#    i-=1
#  bottomRange = i
#  i = maxpos+1
#  lastv = maxvalue
#  while i<256:
#    diff = abs(hist[i]-lastv)
#    if diff <= maxdiff:
#      break
#    lastv=hist[i]
#    i+=1
#  topRange = i
#  return bottomRange,topRange



def _buildHist(filename):
  cap = cv2.VideoCapture(filename)
  hist = np.zeros(256).astype('int64')
  bins=np.asarray(range(257))
  pixelCount = 0.0
  while(cap.isOpened()):
    ret, frame = cap.read()
    if not ret:
      break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pixelCount+=(gray.shape[0]*gray.shape[1])
    hist += np.histogram(gray,bins=bins)[0]
  cap.release()
  return hist,pixelCount

def _buildMasks(filename,histandcount):
  maskprefix = filename[0:filename.rfind('.')]
  histnorm = histandcount[0]/histandcount[1]
  values=np.where((histnorm<=0.95) & (histnorm>(256/histandcount[1])))[0]
  cap = cv2.VideoCapture(filename)
  while(cap.isOpened()):
    ret, frame = cap.read()
    if not ret:
      break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hist = np.histogram(gray,bins=bins)[0]
    result = np.ones(gray.shape)*255
    totalMatch = 0
    for value in values: 
       matches = gray==value
       totalMatch+=sum(sum(matches))
       result[matches]=0
    if totalMatch>0:
       elapsed_time = cap.get(cv2.cv.CV_CAP_PROP_POS_MSEC)
       cv2.imwrite(maskprefix + '_mask_' + str(elapsed_time) + '.png',gray)      
       break
  cap.release()

def buildMasksFromCombinedVideoOld(filename):
  h,pc = _buildHist(filename)
  hist = h/pc
  return _buildMasks(filename,hist)

def buildMasksFromCombinedVideo(filename,codec='mp4v',suffix='mp4'):
  maskprefix = filename[0:filename.rfind('.')]
  capIn = cv2.VideoCapture(filename)
  capOut = None
  try:
    ranges= []
    start = None
    fourcc = cv2.cv.CV_FOURCC(*codec)
    count = 0
    while(capIn.isOpened()):
      ret, frame = capIn.read()
      if not ret:
        break
      elapsed_time = capIn.get(cv2.cv.CV_CAP_PROP_POS_MSEC)
      gray = frame[:,:,1]
#    laplacian = cv2.Laplacian(frame,cv2.CV_64F)
      result = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV, 11, 1)
      ret, otsu = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
      result[:,:]=255
      result[otsu==0] = 0
#      result[otsu==0] = 255
      totalMatch = sum(sum(result))
#      pixels = np.histogram(frame[:,:,1],bins=range(257))[0]
#      unchangedValue =np.where(pixels==max(pixels))[0][0]
#      result = np.ones(gray.shape)*255
#      matches = gray!=unchangedValue
#      totalMatch=sum(sum(matches))
#      result[matches]=0
      if totalMatch>0:
        count+=1
        if start is None:
          start = elapsed_time
          print start
          capOut = cv2.VideoWriter(maskprefix + '_mask_' + str(elapsed_time) + suffix, fourcc, capIn.get(cv2.cv.CV_CAP_PROP_FPS),(result.shape[1],result.shape[0]),False)
#         cv2.imwrite(maskprefix + '_mask_' + str(elapsed_time) + '.png',result)      
        result = result.astype('uint8')
        capOut.write(cv2.cvtColor(result, cv2.COLOR_GRAY2BGR))
      else:
        if start is not None:
          ranges.append((start,elapsed_time,count,maskprefix + '_mask_' + str(start) + suffix))
          capOut.release()
          count = 0
        start = None
        capOut = None
    if start is not None:
      ranges.append((start,elapsed_time,count,maskprefix + '_mask_' + str(start) + suffix))
      capOut.release()
  finally:
    capIn.release()
    if capOut:
      capOut.release()
  return ranges


def addToMeta(meta,prefix,line,split=True):
   parts = line.split(',') if split else [line]
   for part in parts:
     pair = [x.strip().lower() for x in part.split(': ')]
     if len(pair)>1 and pair[1] != '':
       if prefix != '':
         meta[prefix + '.' + pair[0]] = pair[1]
       else:
         meta[pair[0]] = pair[1]
   
def getStreamId(line):
   start = line.find('#')
   if start > 0:
     end = line.find('(',start)
     end = min(end,line.find(': ',start))
     return line[start:end]
   return ''

def processMeta(stream):
   meta = {}
   prefix = ''
   while True:
     line = stream.readline()   
     if line is None or len(line) == 0:
         break
     if 'Stream' in line:
         prefix=getStreamId(line)
         splitPos = line.find(': ')
         meta[line[0:splitPos].strip()] = line[splitPos+2:].strip()
         continue
     if 'Duration' in line:
       addToMeta(meta,prefix, line)
     else:
       addToMeta(meta,prefix, line, split=False)
   return meta

def sortFrames(frames):
   for k,v in frames.iteritems():
    frames[k] = sorted(v,key=lambda meta: meta['pkt_pts_time'])

def _addMetaToFrames(frames,meta):
   if len(meta) > 0 and 'stream_index' in meta:
      index = meta['stream_index']
      if index not in frames:
         frames[index] = []
      frames[index].append(meta)
      meta.pop('stream_index')

def processFrames(stream):
   frames = {}
   meta = {}
   while True:
     line = stream.readline()  
     if line is None or len(line) == 0:
         break
     if '[/FRAME]' in line:
        _addMetaToFrames(frames,meta)
        meta = {}
     else:
         parts = line.split('=')
         if len(parts)>1:
            meta[parts[0].strip()] = parts[1].strip()
   _addMetaToFrames(frames,meta)
   return frames
#   sortFrames(frames)
   
def getMeta(file,withFrames=False):
   ffmpegcommand = os.getenv('MASKGEN_FFPROBETOOL','ffprobe')
   p = Popen([ffmpegcommand,file, '-show_frames'] if withFrames else ['ffprobe',file],stdout=PIPE,stderr=PIPE)
   try:
     frames= processFrames(p.stdout) if withFrames else {}
     meta = processMeta(p.stderr) 
   finally:
     p.stdout.close()
     p.stderr.close()
   return meta,frames

# str(ffmpeg.compareMeta({'f':1,'e':2,'g':3},{'f':1,'y':3,'g':4}))=="{'y': ('a', 3), 'e': ('d', 2), 'g': ('c', 4)}"
def compareMeta(oneMeta,twoMeta,skipMeta=None):
  diff = {}
  for k,v in oneMeta.iteritems():
    if skipMeta is not None and k in skipMeta:
      continue
    if k in twoMeta and twoMeta[k] != v:
      diff[k] = ('change',v, twoMeta[k])
    if k not in twoMeta:
      diff[k] = ('delete',v)
  for k,v in twoMeta.iteritems():
    if k not in oneMeta:
      diff[k] = ('add',v)
  return diff

# video_tools.compareStream([{'i':0,'h':1},{'i':1,'h':1},{'i':2,'h':1},{'i':3,'h':1},{'i':5,'h':2},{'i':6,'k':3}],[{'i':0,'h':1},{'i':3,'h':1},{'i':4,'h':9},{'i':4,'h':2}], orderAttr='i')
# [('delete', 1.0, 2.0, 2), ('add', 4.0, 4.0, 2), ('delete', 5.0, 6.0, 2)]
def compareStream(a,b,orderAttr='pkt_pts_time',skipMeta=None):
  apos = 0
  bpos = 0
  diff = []
  start=0
  while apos < len(a) and bpos < len(b):
    apacket = a[apos]
    aptime = float(apacket[orderAttr])
    bpacket = b[bpos]
    try:
      bptime = float(bpacket[orderAttr])
    except ValueError as e:
      print bpacket
      raise e
    if aptime==bptime:
      metaDiff = compareMeta(apacket,bpacket,skipMeta=skipMeta)
      if len(metaDiff)>0:
        diff.append(('change',apos,bpos,aptime,metaDiff))
      apos+=1
      bpos+=1
    elif aptime < bptime:
      start = aptime
      c = 0
      while aptime < bptime and apos < len(a):
         end = aptime
         apos+=1
         c+=1
         if apos < len(a):
           apacket = a[apos]
           aptime = float(apacket[orderAttr])
      diff.append(('delete',start,end,c))
    elif aptime > bptime:
      start = bptime
      c = 0
      while aptime > bptime and bpos < len(b):
          end = bptime
          c+=1
          bpos+=1
          if bpos < len(b):
            bpacket = b[bpos]
            bptime = float(bpacket[orderAttr])
      diff.append(('add',start,end,c))
  if apos < len(a):
    start = float(a[apos][orderAttr])
    c = 0
    while apos < len(a):
       apacket = a[apos]
       aptime = float(apacket[orderAttr])
       apos+=1
       c+=1
    diff.append(('delete',start,aptime,c))
  elif bpos < len(b):
    start = float(b[bpos][orderAttr])
    c = 0
    while bpos < len(b):
       bpacket = b[apos]
       bptime = float(apacket[orderAttr])
       bpos+=1
       c+=1
    diff.append(('add',start,bptime,c))
  return diff

def compareFrames(oneFrames,twoFrames,skipMeta=None):
  diff = {}
  for streamId, packets in oneFrames.iteritems():
    if streamId in twoFrames:
       diff[streamId] = ('change',compareStream(packets, twoFrames[streamId],skipMeta=skipMeta))
    else:
       diff[streamId] = ('delete',[])
  for streamId, packets in twoFrames.iteritems():
    if streamId not in oneFrames:
       diff[streamId] = ('add',[])
  return diff
    
#video_tools.formMetaDataDiff('/Users/ericrobertson/Documents/movie/videoSample.mp4','/Users/ericrobertson/Documents/movie/videoSample1.mp4')
def formMetaDataDiff(fileOne, fileTwo):
  oneMeta,oneFrames = getMeta(fileOne,withFrames=True)
  twoMeta,twoFrames = getMeta(fileTwo,withFrames=True)
  metaDiff = compareMeta(oneMeta,twoMeta)
  frameDiff = compareFrames(oneFrames, twoFrames, skipMeta=['pkt_pos','pkt_size'])
  return metaDiff,frameDiff

#video_tools.processSet('/Users/ericrobertson/Documents/movie',[('videoSample','videoSample1'),('videoSample1','videoSample2'),('videoSample2','videoSample3'),('videoSample4','videoSample5'),('videoSample5','videoSample6'),('videoSample6','videoSample7'),('videoSample7','videoSample8'),('videoSample8','videoSample9'),('videoSample9','videoSample10'),('videoSample11','videoSample12'),('videoSample12','videoSample13'),('videoSample13','videoSample14'),('videoSample14','videoSample15')] ,'.mp4')
def processSet(dir,set,postfix):
  first = None
  for pair in set:
    print pair
    resMeta,resFrame = formMetaDataDiff(os.path.join(dir,pair[0]+postfix),os.path.join(dir,pair[1]+postfix))
    resultFile = os.path.join(dir,pair[0] + "_" + pair[1] + ".json")
    with open(resultFile, 'w') as f:
       json.dump({"meta":resMeta,"frames":resFrame},f,indent=2)


#video_tools.formMaskDiff('/Users/ericrobertson/Documents/movie/s1/videoSample5.mp4','/Users/ericrobertson/Documents/movie/s1/videoSample6.mp4')
def formMaskDiff(fileOne, fileTwo):
   ffmpegcommand = os.getenv('MASKGEN_FFMPEGTOOL','ffmpeg')
   prefixOne = fileOne[0:fileOne.rfind('.')]
   prefixTwo = os.path.split(fileTwo[0:fileTwo.rfind('.')])[1]
   postFix = fileOne[fileOne.rfind('.'):]
   outFileName = prefixOne + '_'  + prefixTwo + postFix
   call([ffmpegcommand, '-y', '-i', fileOne, '-i', fileTwo, '-filter_complex', 'blend=all_mode=difference', outFileName])  
   buildMasksFromCombinedVideo(outFileName)

