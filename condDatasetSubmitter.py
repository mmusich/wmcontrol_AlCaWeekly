#! /usr/bin/env python

import ast
import os
import sys
import re
from optparse import OptionParser
import datetime
import json

sys.path.append('/afs/cern.ch/cms/PPD/PdmV/tools/prod/devel/')
from phedex import phedex

from modules import wma

DRYRUN=False

#-------------------------------------------------------------------------------

def createOptionParser():
  global DRYRUN
  usage=\
  """
  ConditionValidation.py --gt <GT> [ either: --run <run> or: --runLs <runLumiDict>] --conds <condition json>
  """

  parser = OptionParser(usage)
  parser.add_option("--newgt",
                    dest="newgt",
                    help="new global tag containing tag to be tested")
  parser.add_option("--gt",
                    dest="gt",
                    help="common/reference global tag to both submissions")
  parser.add_option("--basegt",
                    dest="basegt",
                    default="",
                    help="common global tag to base RECO+HLT/HLT+RECO submissions")
  parser.add_option("--run",
                    help="the run number to be processed, can be a comma separated list")
  parser.add_option("--runLs",
                    help="the dictionary of run numbers mapped to lists of lumi sections (standard CMS certification json format)")
  parser.add_option("--ds",
                    help="dataset to be processed",
                    default="/MinimumBias/Run2012B-PromptReco-v1/RECO")
  parser.add_option("--conds",
                    help="List of new tag,record,connection_string triplets to be tested")
  parser.add_option("--dry",
                    default=False,
                    action='store_true')
  parser.add_option("--Type",
                    help="Defines the type of the workflow",
                    choices=['HLT','PR','PR+ALCA','RECO+HLT','HLT+RECO','HLT+RECO+ALCA'],
                    default='HLT')
  parser.add_option("--HLT",
                    help="Specify which default HLT menu: SameAsRun uses the HLT menu corrresponding to the run, Custom lets you choose it explicitly",
                    choices=['SameAsRun','GRun','50nsGRun','Custom','25ns14e33_v3'],
                    default=None)
  parser.add_option("--B0T",
                    default=False,
                    help="Specify 0T reconstruction",
                    action='store_true')
  parser.add_option("--HIon",
                    default=False,
                    help="Specify HIon reconstruction",
                    action='store_true')
  parser.add_option("--HLTCustomMenu",
                    help="Specify a custom HLT menu",
                    default=None)  
  parser.add_option("--string",
                    help="Processing string to add to dataset name (default is current date)",
                    default=None)
  parser.add_option("--recoCmsswDir",
                    help="CMSSW base directory for RECO step if different from HLT step (supported for HLT+RECO type)",
                    default=None)
  parser.add_option("--noSiteCheck",
                    help="Prevents the site check to be operated",
                    default=False,
                    action='store_true')
                     
  (options,args) = parser.parse_args()
#  print "** options args"
#  print options
#  print args
#  print "** options args"
  
#  if not options.gt or not options.run or not options.conds:
#      parser.error("options --run, --gt and --conds are mandatory")
  if not options.newgt or not options.gt or not ( options.run or options.runLs):
      parser.error("options --newgt,  [ either: --run  or: --runLs ], and --gt  are mandatory")
  
  print "** runLs"
  print options.runLs
  print "** runLs"
  if (options.runLs):
    options.runLs = eval(options.runLs)

  CMSSW_VERSION='CMSSW_VERSION'
  if not os.environ.has_key(CMSSW_VERSION):
    print "\n CMSSW not properly set. Exiting"
    sys.exit(1)
  options.release = os.getenv(CMSSW_VERSION)

  CMSSW_BASE='CMSSW_BASE'
  options.hltCmsswDir = os.getenv(CMSSW_BASE)

  options.recoRelease = None
  if options.recoCmsswDir:
    options.recoRelease = getCMSSWReleaseFromPath( options.recoCmsswDir )
  else:
    options.recoRelease = getCMSSWReleaseFromPath( options.hltCmsswDir )
    # if a release is not provided for the reco step (RECO or PR), use the only release known hltCmsswDir

  if options.dry:
    DRYRUN=True

  options.ds=options.ds.split(',')
  if (options.run): options.run = options.run.split(',')
  # FIX FIX: can I act here to save the day and handle propetly the dictionary case ?
  print "OPOP options.run"
  print options.run
  print "OPOP options.run"
  return options

#-------------------------------------------------------------------------------

def getConfCondDictionary(conditions_filename):
  # read the tags fromt eh list
  #newCtags=eval(open(options.conds).read())
  
  ConfCondList=[ ('REFERENCE.py',options.gt) ]
  ConfCondDictionary={
      'REFERENCE.py':options.gt
      }
    
  #for (i,condbunch) in enumerate(newCtags):
  #    ConfCondDictionary['NEWCONDITIONS%s.py'%i]='%s'%('+'.join(map(lambda r : ','.join(r),condbunch)))
  #    ConfCondList.append( ('NEWCONDITIONS%s.py'%i, '%s'%('+'.join(map(lambda r : ','.join(r),condbunch))) ) )

  ConfCondDictionary['NEWCONDITIONS0.py']=options.newgt
  ConfCondList.append( ('NEWCONDITIONS0.py', options.newgt ) ) 
  #return ConfCondDictionary
  return ConfCondList

#-------------------------------------------------------------------------------

def isPCLReady(run):
  #mydict = json.loads(os.popen('curl -L --cookie ~/private/ssocookie.txt --cookie-jar ~/private/ssocookie.txt https://cms-conddb-prod.cern.ch/pclMon/get_latest_runs?run_class=Cosmics% -k').read())

  #print mydict
  
  #for line in os.popen('curl -s http://cms-alcadb.web.cern.ch/cms-alcadb/Monitoring/PCLTier0Workflow/log.txt').read().split('\n'):
  #  if not line: continue
  #  spl=line.split()
  #  if spl[0]==str(run):
  #    ready=eval(spl[7])
  #    print "\n\n\tPCL ready for ",run,"\n\n"
  #    return ready
  
  return False

def isAtSite(ds, run):
  blocks=[]
  ph=phedex(ds)
  # get list of blocks for input dataset directly from DBS3
  # documentation: https://cmsweb.cern.ch/dbs/prod/global/DBSReader/
  connection = wma.init_connection('cmsweb.cern.ch')
  blockDicts = ast.literal_eval(
    wma.httpget(connection, wma.DBS3_URL+"blocks?dataset=%s&run_num=%s"%(ds,run)) ) # connection return a string which represents a list
  print "INI inside isAtSite"
  print run
  print blockDicts
  print "END inside isAtSite"

  for blockDict in blockDicts:
      block = blockDict['block_name']
      # print "block is: %s"%block

      # it's unclear what probing custodiality means; remove this check  
      #
      #for b in filter(lambda b :b.name==block,ph.block):
      #  for replica in filter(lambda r : r.custodial=='y',b.replica):
      #    if replica.complete!='y':
      #      print block,'not complete at custodial site'
      #      #print block,'not complete at custodial site but ignoring'
      #      #blocks.append('#'+block.split('#')[-1])
      #    else:
      #      print block,'complete at custodial site'
      #      blocks.append('#'+block.split('#')[-1])

      blocks.append('#'+block.split('#')[-1])

  if len(blocks)==0:
    print "No possible block for %s in %s"%(run,ds)
    return False
  else:
    print "\n\n\t Block testing succeeded for %s in %s \n\n"%(run,ds)
    print blocks
    return list(set(blocks))

#-------------------------------------------------------------------------------
## decommissionned because we could run anywhere
#def checkIsAtFnal(run, ds):
#  if not isAtFnal (run, ds):
#    print "Run %s of %s is not at fnal. Impossible to continue." %(run, ds)
#    sys.exit(1)

#-------------------------------------------------------------------------------

# we need this check to handle the discontinued customise functions
def isCMSSWBeforeEight( theRelease ):
  if theRelease == None :
    raise ValueError('theRelease is set to %s and yet, it seems to be required. ERRROR.' % (theRelease))
  if int(theRelease.split("_")[1]) < 8 :
    return True
  elif int(theRelease.split("_")[1]) == 8 :
    return int( theRelease.split("_")[2] ) < 1  and int( theRelease.split("_")[3] ) < 1
  else :
    return False

def is_hltGetConfigurationOK ( theRelease ):
  if theRelease == None :
    raise ValueError('theRelease is set to %s and yet, it seems to be required. ERRROR.' % (theRelease))
  if int(theRelease.split("_")[1]) > 8 :
    return True
  if int(theRelease.split("_")[1]) == 8 :
    return int( theRelease.split("_")[2] ) < 1  and int( theRelease.split("_")[3] ) >= 9
  else :
    return False
  
def getCMSSWReleaseFromPath( thePath ):
  path_list = thePath.split('/')
  for path in path_list:
    if path.find("CMSSW")!=-1:
      return path
  raise ValueError('%s does not contain a slash-separated path to a CMSSW release. ERRROR.' % (thePath))

def getDriverDetails(Type,B0T,HIon,recoRelease):
  HLTBase= {"reqtype":"HLT",
            "steps":"L1REPACK:Full,HLT,DQM", #replaced DQM:triggerOfflineDQMSource with DQM
            "procname":"HLT2",
            "datatier":"FEVTDEBUGHLT,DQM ",
            "eventcontent":"FEVTDEBUGHLT,DQM",
            "inputcommands":'keep *,drop *_hlt*_*_HLT,drop *_TriggerResults_*_HLT,,drop *_*_*_RECO',
            "era":'Run2_2016',
            #"custcommands":'process.schedule.remove( process.HLTriggerFirstPath )',
            "custcommands":"process.load('Configuration.StandardSequences.Reconstruction_cff'); " +\
                           "process.hltTrackRefitterForSiStripMonitorTrack.src = 'generalTracks'; " +\
                           "\ntry:\n\tif process.RatesMonitoring in process.schedule: process.schedule.remove( process.RatesMonitoring );\nexcept: pass",
            "custconditions":"JetCorrectorParametersCollection_CSA14_V4_MC_AK4PF,JetCorrectionsRecord,frontier://FrontierProd/CMS_CONDITIONS,AK4PF",
            "magfield":"",
            "dumppython":False,
            "inclparents":"True"}
  if B0T:
    HLTBase.update({"magfield":"0T"})    # this should not be needed - it's GT-driven FIX GF
  HLTRECObase={"steps":"RAW2DIGI,L1Reco,RECO",
               "procname":"reRECO",
               "datatier":"RAW-RECO", # why RAW-RECO here while RECO elsewhere ?
               "eventcontent":"RAWRECO",
               "inputcommands":'',
               "custcommands":'',
               }

  if options.HLT:
    HLTBase.update({"steps":"HLT:%s,DQM"%(options.HLT),
                    "dumppython":True}) 
  if Type=='HLT':
    return HLTBase
  elif Type=='RECO+HLT':
    HLTBase.update({'base':HLTRECObase})
    return HLTBase
  elif Type in ['HLT+RECO','HLT+RECO+ALCA']:
    if options.HLT:
      HLTBase.update({"steps":"L1REPACK:Full,HLT:%s"%(options.HLT),
                      "custcommands":"\ntry:\n\tif process.RatesMonitoring in process.schedule: process.schedule.remove( process.RatesMonitoring );\nexcept: pass",
                      "custconditions":"",
                      #"output":'[{"e":"RAW","t":"RAW","o":["drop FEDRawDataCollection_rawDataCollector__LHC"]}]',
                      "output":'',
                      #"datatier":"RAW",
                      #"eventcontent":"RAW",
                      "dumppython":True})
    else:
      HLTBase.update({"steps":"L1REPACK:Full,HLT",
                      "custcommands":"\ntry:\n\tif process.RatesMonitoring in process.schedule: process.schedule.remove( process.RatesMonitoring );\nexcept: pass",
                      "custconditions":"",
                      #"datatier":"RAW",
                      #"eventcontent":"RAW",
                      "magfield":""})
    HLTRECObase={"steps":"RAW2DIGI,L1Reco,RECO,DQM",
                "procname":"reRECO",
                 "datatier":"RECO,DQMIO",
                 "eventcontent":"RECO,DQM",
                 #"inputcommands":'keep *',
                 "inputcommands":'',
                 "custcommands":'',
                 "custconditions":'',
                 "customise":'',
                 #"customise":"Configuration/DataProcessing/RecoTLR.customisePromptRun2Deprecated",
                 "era":"Run2_2016",
                 "magfield":"",
                 "dumppython":False}
    # keep backward compatibility with releases earlier than 8_0_x

    if isCMSSWBeforeEight( recoRelease ) :
      raise ValueError('theRelease is set to %s, which is not supported by condDatasetSubmitter' % (recoRelease))

    if B0T:
      pass
      # HLTRECObase.update({"magfield":"0T"})

    if HIon:
      raise ValueError('condDatasetSubmitter is not yet set up to run HI validations - e-tutto-lavoraccio')

    if Type=='HLT+RECO+ALCA':
        HLTRECObase.update({"steps":"RAW2DIGI,L1Reco,RECO,ALCA:SiStripCalMinBias,DQM"})
    HLTBase.update({'recodqm':HLTRECObase})    
    return HLTBase
  elif Type in ['PR','PR+ALCA']:
    theDetails={"reqtype":"PR",
                "steps":"RAW2DIGI,L1Reco,RECO,DQM",
                "procname":"reRECO",
                "datatier":"RECO,DQMIO ",
                "output":'',
                "eventcontent":"RECO,DQM",
                #"inputcommands":'keep *',
                "inputcommands":'',
                "custcommands":'',
                "custconditions":'',        
                "customise":'',
                #"customise":"Configuration/DataProcessing/RecoTLR.customisePromptRun2Deprecated",
                "era":"Run2_2016",
                "magfield":"",
                "dumppython":False,
                "inclparents":"False"}      

    if isCMSSWBeforeEight( recoRelease ) :
      raise ValueError('theRelease is set to %s, which is not supported by condDatasetSubmitter' % (recoRelease))


    if B0T:
      pass
        #theDetails.update({"magfield":"0T",
        #                    "customise":"Configuration/DataProcessing/RecoTLR.customisePromptRun2DeprecatedB0T"})

    if HIon:        
      raise ValueError('condDatasetSubmitter is not yet set up to run HI validations - e-tutto-lavoraccio')
    # WHICH ERA HERE ???


    if Type=='PR+ALCA':
        theDetails.update({"steps":"RAW2DIGI,L1Reco,RECO,ALCA:SiStripCalMinBias,DQM"})
    return theDetails

#-------------------------------------------------------------------------------

def execme(command):
  if DRYRUN:
    print command
  else:
    print " * Executing: %s..."%command
    os.system(command)
    print " * Executed!"

#-------------------------------------------------------------------------------
def createHLTConfig(options):

  assert  os.path.exists("%s/src/HLTrigger/Configuration/"%(options.hltCmsswDir) ), "error: HLTrigger/Configuration/ is missing in the CMSSW release for HLT (set to: echo $CMSSW_VERSION ) - can't create the HLT configuration "
  
  onerun=0
  if      (options.run):    onerun = options.run[0]
  elif    (options.runLs):  onerun = options.runLs.keys()[0]
#  elif    (options.runLs):  onerun = eval(options.runLs).keys()[0]

  if options.HLT=="SameAsRun":
    hlt_command="hltGetConfiguration --unprescale --cff --offline " +\
                "run:%s "%onerun +\
                "> %s/src/HLTrigger/Configuration/python/HLT_%s_cff.py"%(options.hltCmsswDir,options.HLT)
                
  elif options.HLT=="Custom":
    hlt_command="hltGetConfiguration --unprescale --cff --offline " +\
                "%s "%options.HLTCustomMenu +\
                "> %s/src/HLTrigger/Configuration/python/HLT_%s_cff.py"%(options.hltCmsswDir,options.HLT)
      
  cmssw_command = "cd %s; eval `scramv1 runtime -sh`; cd -"%options.hltCmsswDir
  build_command = "cd %s/src; eval `scramv1 runtime -sh`; scram b; cd -"%options.hltCmsswDir

  patch_command = "sed -i 's/+ fragment.hltDQMFileSaver//g' %s/src/HLTrigger/Configuration/python/HLT_%s_cff.py"%(options.hltCmsswDir,options.HLT)
  patch_command2 = "sed -i 's/, fragment.DQMHistograms//g' %s/src/HLTrigger/Configuration/python/HLT_%s_cff.py"%(options.hltCmsswDir,options.HLT)

  if ( is_hltGetConfigurationOK(  getCMSSWReleaseFromPath( options.hltCmsswDir ) ) ):
    execme(cmssw_command + '; ' + hlt_command + '; ' + build_command )
  else:
    execme(cmssw_command + '; ' + hlt_command + '; ' + patch_command + '; ' + patch_command2 + '; ' + build_command )
    print "\n CMSSW release for HLT doesn't allow usage of hltGetConfiguration out-of-the-box, patching configuration "

def createCMSSWConfigs(options,confCondDictionary,allRunsAndBlocks):
  details=getDriverDetails(options.Type,options.B0T,options.HIon,options.recoRelease)

  # get processing string
  if options.string is None:
    processing_string = str(datetime.date.today()).replace("-","_") + "_" + str(datetime.datetime.now().time()).replace(":","_")[0:5] 
    #processing_string = str(datetime.date.today()).replace("-","_") # GF: check differentiation between steps VS step{2}_processstring
  else:
    processing_string = options.string # GF: check differentiation between steps VS step{2}_processstring

    
  scenario = '--scenario pp'
  if options.HIon:
    scenario = '--scenario HeavyIons --repacked'
    
  # Create the drivers
  #print confCondDictionary
  #for cfgname,custconditions in confCondDictionary.items():

  for c in confCondList:
    (cfgname,custgt) = c
    print "\n\n\tCreating for",cfgname,"\n\n"
    driver_command="cmsDriver.py %s " %details['reqtype']+\
       "-s %s " %details['steps'] +\
       "--processName %s " % details['procname'] +\
       "--data %s "%scenario +\
       "--datatier %s " % details['datatier'] +\
       "--conditions %s " %custgt +\
       "--python_filename %s " %cfgname +\
       "--no_exec " +\
       "-n 100 "
    if details['eventcontent']:      
       driver_command += "--eventcontent %s " %details['eventcontent']  
    if details['output']!='':      
       driver_command += "--output '%s' " %details['output']  
    if details['dumppython']:
       driver_command += "--dump_python "
    if 'customise' in details.keys() and details['customise']!='': 
      driver_command += '--customise %s '%details['customise']
    if details['era']!="" :
      driver_command += "--era %s " % details['era']
    if details['magfield']!="":
      driver_command += '--magField %s '%details['magfield']
    if details['inputcommands']!="":
      driver_command += '--inputCommands "%s" '%details['inputcommands']
    if details['custconditions']!="":
      driver_command += '--custom_conditions="%s" ' %details['custconditions']
    if details['custcommands']!="":
      driver_command += '--customise_commands="%s" ' %details['custcommands']


    cmssw_command = "cd %s; eval `scramv1 runtime -sh`; cd -"%options.hltCmsswDir
    upload_command = "wmupload.py -u %s -g PPD -l %s %s"% (os.getenv('USER'),cfgname,cfgname)
    execme(cmssw_command + '; ' + driver_command + '; ' + upload_command)
    
    base=None
    if 'base' in details:
      base=details['base']
      driver_command="cmsDriver.py %s " %details['reqtype']+\
                      "-s %s " %base['steps'] +\
                      "--processName %s " % base['procname'] +\
                      "--data %s "%scenario +\
                      "--datatier %s " % base['datatier'] +\
                      "--eventcontent %s " %base['eventcontent']  +\
                      "--conditions %s " %options.basegt +\
                      "--python_filename reco.py " +\
                      "--no_exec " +\
                      "-n 100 "
      execme(driver_command)
      
    recodqm = None
    if 'recodqm' in details:
      recodqm=details['recodqm']
      driver_command="cmsDriver.py %s " %details['reqtype']+\
                      "-s %s " %recodqm['steps'] +\
                      "--processName %s " % recodqm['procname'] +\
                      "--data %s "%scenario +\
                      "--datatier %s " % recodqm['datatier'] +\
                      "--eventcontent %s " %recodqm['eventcontent']  +\
                      "--conditions %s " %options.basegt +\
                      "--hltProcess HLT2 " +\
                      "--filein=file:HLT_HLT.root " +\
                      "--python_filename recodqm.py " +\
                      "--no_exec " +\
                      "-n 100 "                 

      if 'customise' in recodqm.keys() and recodqm['customise']!="" : 
        driver_command += "--customise %s " % recodqm['customise']
      if recodqm['era']!="" :
        driver_command += "--era %s " % recodqm['era']
      if recodqm['dumppython']:
        driver_command += "--dump_python "
      if recodqm['magfield']!="":
        driver_command += "--magField %s " % recodqm['magfield']
      if recodqm['custcommands']!="":
        driver_command += "--customise_commands='%s' " % recodqm['custcommands']     
      if options.recoCmsswDir:
        cmssw_command = "cd %s; eval `scramv1 runtime -sh`; cd -"%options.recoCmsswDir        
        upload_command = "wmupload.py -u %s -g PPD -l %s %s"% (os.getenv('USER'),'recodqm.py','recodqm.py')
        execme(cmssw_command + '; ' + driver_command + '; ' + upload_command)
      else:
        execme(driver_command)
        
      if options.Type.find("ALCA")!=-1:          
          filein = "%s_RAW2DIGI_L1Reco_RECO_ALCA_DQM_inDQM.root"%details['reqtype']
      else:        
          filein = "%s_RAW2DIGI_L1Reco_RECO_DQM_inDQM.root"%details['reqtype'] 
          
      driver_command="cmsDriver.py step4 " +\
                      "-s HARVESTING:dqmHarvesting " +\
                      "--data %s "%scenario +\
                      "--filetype DQM " +\
                      "--conditions %s "%options.basegt +\
                      "--filein=file:%s "%filein +\
                      "--python_filename=step4_%s_HARVESTING.py "%label +\ 
                      "--no_exec " +\
                      "-n 100 "
                      
      if options.recoCmsswDir:
        cmssw_command = "cd %s; eval `scramv1 runtime -sh`; cd -"%options.recoCmsswDir
        upload_command = "wmupload.py -u %s -g PPD -l %s %s"% (os.getenv('USER'),'step4_%s_HARVESTING.py'%label,'step4_%s_HARVESTING.py'%label) 
        execme(cmssw_command + '; ' + driver_command + '; ' + upload_command)
      else:
        execme(driver_command)
    else:      
      if options.Type.find("ALCA")!=-1:
          filein = "%s_RAW2DIGI_L1Reco_RECO_ALCA_DQM_inDQM.root"%details['reqtype']
      else:
          filein = "%s_RAW2DIGI_L1Reco_RECO_DQM_inDQM.root"%details['reqtype'] 
      driver_command="cmsDriver.py step4 " +\
                      "-s HARVESTING:dqmHarvesting " +\
                      "--data %s "%scenario +\
                      "--filetype DQM " +\
                      "--conditions %s "%custgt +\
                      "--filein=file:%s "%filein +\
                      "--python_filename=step4_%s_HARVESTING.py "%label +\
                      "--no_exec " +\
                      "-n 100 "
      execme(driver_command)
                      
          
      

  #matched=re.match("(.*)::All",options.gt)
  #gtshort=matched.group(1)
  matched=re.match("(.*),(.*),(.*)",options.newgt)
  if matched: 
    gtshort=matched.group(1)
  else:
    gtshort=options.newgt
    
  matched=re.match("(.*),(.*),(.*)",options.gt)
  if matched: 
    refgtshort=matched.group(1)
  else:
    refgtshort=options.gt
    
  if base:
    subgtshort = gtshort
    refsubgtshort = refgtshort
    #matched=re.match("(.*)::All",options.basegt)
    #gtshort=matched.group(1)
    matched=re.match("(.*),(.*),(.*)",options.basegt)
    if matched:
      gtshort=matched.group(1)
    else:
      gtshort=options.basegt
      
  if recodqm:
    subgtshort = gtshort
    refsubgtshort = refgtshort
    #matched=re.match("(.*)::All",options.basegt)
    #gtshort=matched.group(1)
    matched=re.match("(.*),(.*),(.*)",options.basegt)
    if matched:
      gtshort=matched.group(1)
    else:
      gtshort=options.basegt

    
  
  # Creating the WMC cfgfile
  wmcconf_text= '[DEFAULT] \n'+\
                'group=ppd \n'+\
                'user=%s\n' %os.getenv('USER')
  if base or recodqm:
    wmcconf_text+='request_type= TaskChain \n'
  else:
    wmcconf_text+='request_type= TaskChain \n'#+\
#                  'includeparents = %s \n' %details['inclparents']
  if recodqm:
    wmcconf_text+='priority = 900000 \n'+\
                  'release=%s\n' %options.release +\
                  'globaltag =%s \n' %subgtshort
  else:
    wmcconf_text+='priority = 900000 \n'+\
                  'release=%s\n' %options.release +\
                  'globaltag =%s \n' %gtshort
  wmcconf_text+='dset_run_dict= {'
  for ds in options.ds:
    # if options.run is not specified and runLs is, simply leave the list of runs blank
    if (options.run): wmcconf_text+='"%s" : [%s],\n '%(ds, ','.join(options.run+ map(lambda s :'"%s"'%(s),allRunsAndBlocks[ds])))
    else            : wmcconf_text+='"%s" : [],\n '%(ds)
    wmcconf_text+='}\n'
  print "\nwmconf_text IN THE MAKING"
  print  wmcconf_text
  print "wmconf_text IN THE MAKING\n"
  wmcconf_text+='dqmuploadurl = https://cmsweb.cern.ch/dqm/relval\n\n'

  onerun=0
  if      (options.run):    onerun = options.run[0]
  elif    (options.runLs):  onerun = options.runLs.keys()[0]

  if base:
    wmcconf_text+='[HLT_validation]\n'+\
                   'cfg_path = reco.py\n' +\
                   'req_name = %s_RelVal_%s\n'%(details['reqtype'],onerun) +\
                   '\n\n'
  elif recodqm:
    pass
  else:
    wmcconf_text+='[%s_reference]\n' %details['reqtype'] +\
                   'keep_step1 = True\n' +\
                   'time_event = 10\n' +\
                   'size_memory = 3000\n' +\
                   'step1_lumisperjob = 1\n' +\
                   'processing_string = %s_%sref_%s \n'%(processing_string,details['reqtype'],refgtshort) +\
                   'cfg_path = REFERENCE.py\n' +\
                   'req_name = %s_reference_RelVal_%s\n'%(details['reqtype'],onerun) +\
                   'globaltag = %s\n'%(refgtshort) +\
                   'harvest_cfg=step4_refer_HARVESTING.py\n\n' # this is ugly and depends on [0:5]; can't be easliy fixed w/o reorganization 
    if (options.runLs):
      wmcconf_text+='lumi_list=%s\n\n'%(options.runLs)

  task=2
  print confCondList
  for (i,c) in enumerate(confCondList):
    cfgname=c[0]
    if "REFERENCE" in cfgname:
      if base:
        wmcconf_text+='step%d_output = RAWRECOoutput\n'%task +\
                       'step%d_cfg = %s\n'%(task,cfgname) +\
                       'step%d_globaltag = %s\n'%(task,refsubgtshort) +\
                       'step%d_input = Task1\n\n'%task
        task+=1
        continue
      elif recodqm:
        label=cfgname.lower().replace('.py','')[0:5]
        wmcconf_text+='\n\n[%s_%s]\n' %(details['reqtype'],label) +\
                       'keep_step%d = True\n'%task +\
                       'time_event = 1\n' +\
                       'size_memory = 3000\n' +\
                       'step1_lumisperjob = 10\n' +\
                       'processing_string = %s_%s_%s \n'%(processing_string,details['reqtype']+label,refsubgtshort) +\
                       'cfg_path = %s\n'%cfgname +\
                       'req_name = %s_%s_RelVal_%s\n'%(details['reqtype'],label,onerun) +\
                       'globaltag = %s\n'%(refsubgtshort) +\
                       'step%d_output = FEVTDEBUGHLToutput\n'%task +\
                       'step%d_cfg = recodqm.py\n'%task +\
                       'step%d_lumisperjob = 1\n'%task +\
                       'step%d_globaltag = %s \n'%(task,gtshort) +\
                       'step%d_processstring = %s_%s_%s \n'%(task,processing_string,details['reqtype']+label,refsubgtshort) +\
                       'step%d_input = Task1\n'%task +\
                       'step%d_timeevent = 10\n'%task
        if options.recoRelease:
          wmcconf_text+='step%d_release = %s \n'%(task,options.recoRelease)
        wmcconf_text+='harvest_cfg=step4_%s_HARVESTING.py\n\n'%label 
        if (options.runLs):
          wmcconf_text+='lumi_list=%s\n\n'%(options.runLs)
      else:
        continue

    if base:
      wmcconf_text+='\n\n' +\
                     'step%d_output = RAWRECOoutput\n'%task +\
                     'step%d_cfg = %s\n'%(task,cfgname) +\
                     'step%d_globaltag = %s\n'%(task,subgtshort) +\
                     'step%d_input = Task1\n\n'%task
      task+=1
    elif recodqm:
      if "REFERENCE" in cfgname: continue
      label=cfgname.lower().replace('.py','')[0:5]
      wmcconf_text+='\n\n[%s_%s]\n' %(details['reqtype'],label) +\
                     'keep_step%d = True\n'%task +\
                     'time_event = 1\n' +\
                     'size_memory = 3000\n' +\
                     'step1_lumisperjob = 10\n' +\
                     'processing_string = %s_%s_%s \n'%(processing_string,details['reqtype']+label,subgtshort) +\
                     'cfg_path = %s\n'%cfgname +\
                     'req_name = %s_%s_RelVal_%s\n'%(details['reqtype'],label,onerun) +\
                     'globaltag = %s\n'%(subgtshort) +\
                     'step%d_output = FEVTDEBUGHLToutput\n'%task +\
                     'step%d_cfg = recodqm.py\n'%task +\
                     'step%d_lumisperjob = 1\n'%task +\
                     'step%d_globaltag = %s \n'%(task,gtshort) +\
                     'step%d_processstring = %s_%s_%s \n'%(task,processing_string,details['reqtype']+label,subgtshort) +\
                     'step%d_input = Task1\n'%task +\
                     'step%d_timeevent = 10\n'%task
      if options.recoRelease:
        wmcconf_text+='step%d_release = %s \n'%(task,options.recoRelease)
      wmcconf_text+='harvest_cfg=step4_%s_HARVESTING.py\n\n'%label 
      if (options.runLs):
        wmcconf_text+='lumi_list=%s\n\n'%(options.runLs)

    else:
      label=cfgname.lower().replace('.py','')[0:5]
      wmcconf_text+='\n\n[%s_%s]\n' %(details['reqtype'],label) +\
                     'keep_step1 = True\n' +\
                     'time_event = 10\n' +\
                     'size_memory = 3000\n' +\
                     'step1_lumisperjob = 1\n' +\
                     'processing_string = %s_%s_%s \n'%(str(datetime.date.today()).replace("-","_"),details['reqtype']+label,gtshort) +\
                     'cfg_path = %s\n'%cfgname +\
                     'req_name = %s_%s_RelVal_%s\n'%(details['reqtype'],label,onerun) +\
                     'globaltag = %s\n'%(gtshort) +\
                     'harvest_cfg=step4_%s_HARVESTING.py\n'%label
      if (options.runLs):
        wmcconf_text+='lumi_list=%s\n\n'%(options.runLs)
                
# FIX FIX FIX      
# FOLLOW NAMING CONVENTION OF FILE FROM relval_submit.py
#  run_label_for_FN = '' options.run[0]
      
#  run_label_for_FN = ''
#  if isinstance(options.run, dict) or isinstance(options.run, list):
#    for oneRun in options.run:
#      if run_label_for_FN != '':
#        run_label_for_FN += '_'
#        run_label_for_FN += str(oneRun)
#      if isinstance(options.run, dict):
#            run_label_for_FN +='_ls'
#      if isinstance(options.run, int):
#            run_label_for_FN = int(options.run)
#      if isinstance(options.run, str):
#            run_label_for_FN = options.run

  run_label_for_fn = ''
  # if run is int => single label; if run||runLs are list or dict, _-separated composite label
  
  if  options.run:
    print "run is "
    print options.run
    print "run is "
  if options.run and isinstance( options.run, int):
    run_label_for_fn = options.run
  elif options.run and isinstance( options.run, list) :
    #thisRunKey = 'run'
    #if 'runLs' in options:
    #  thisRunKey = 'runLs'
    for oneRun in options.run:
      if run_label_for_fn != '':
        run_label_for_fn += '_'
      run_label_for_fn += str(oneRun)
  elif options.runLs and isinstance( options.runLs, dict) :
    for oneRun in options.runLs:
      if run_label_for_fn != '':
        run_label_for_fn += '_'
      run_label_for_fn += str(oneRun)

#  if 'run' in metadata['options'] and isinstance( metadata['options']['run'], int):
#    run_label_for_fn = metadata['options']['run']
#  else:
#    thisRunKey = 'run'
#    if 'runLs' in metadata['options']:
#      thisRunKey = 'runLs'
#      for oneRun in metadata['options'][thisRunKey]:
#        if run_label_for_fn != '':
#          run_label_for_fn += '_'
#        run_label_for_fn += str(oneRun)
  wmconf_name='%sConditionValidation_%s_%s_%s.conf'%(details['reqtype'],
                                                      options.release,
                                                      gtshort,
                                                      run_label_for_fn) # FOLLOW NAMING CONVENTION OF FILE FROM relval_submit.py
  print "*** run_label_for_fn "
  print wmconf_name
  print "*** run_label_for_FN "
  # FIX FIX FIX 

  if not DRYRUN:
    wmcconf=open(wmconf_name,'w')    
    wmcconf.write(wmcconf_text)
    wmcconf.close()
  
  #execme('wmcontrol.py --test --req_file %s'%wmconf_name)
  #print 'Now execute:\nwmcontrol.py --req_file %s'%wmconf_name  
  execme('./wmcontrol.py --test --req_file %s'%wmconf_name)
  print 'Now execute:\n./wmcontrol.py --req_file %s'%wmconf_name  

def printInfo(options):

  
  if "HLT" in options.Type:
    if options.HLT is not None:
      hltFilename = '%s/src/HLTrigger/Configuration/python/HLT_%s_cff.py'%(options.hltCmsswDir,options.HLT)
    else:    
      hltFilename = '%s/src/HLTrigger/Configuration/python/HLT_GRun_cff.py'%(options.hltCmsswDir)
    f = open(hltFilename)
    menu = f.readline()
    menu = menu.replace('\n','').replace('# ','')
    menulist = menu.split()
    hltCmsswVersion = (options.hltCmsswDir).split('/')
    menulist[-1] = '(%s)'%(hltCmsswVersion[-1]) 
    menu = menulist[0] + " " + menulist[-1]

  matched=re.match("(.*),(.*),(.*)",options.newgt)
  if matched: 
    newgtshort=matched.group(1)
  else:
    newgtshort=options.newgt
    
  matched=re.match("(.*),(.*),(.*)",options.gt)
  if matched: 
    gtshort=matched.group(1)
  else:
    gtshort=options.gt
    
  print ""
  print "type: %s"%options.Type
  print "dataset: %s"%",".join(options.ds)
  if (options.run):     print "run: %s"%",".join(options.run)
  elif (options.runLs): print "run: %s"%(options.runLs)
  if "HLT" in options.Type:
    print "HLT menu: %s"%menu
    print "Target HLT GT: %s"%newgtshort
    print "Reference HLT GT: %s"%gtshort  
  if "HLT" in options.Type and "RECO" in options.Type:
    print "Common Prompt GT: %s"%options.basegt
  if "PR" in options.Type:    
    print "Target Prompt GT: %s"%newgtshort
    print "Reference Prompt GT: %s"%gtshort

#-------------------------------------------------------------------------------

if __name__ == "__main__":
  #Raise an error if couchID files exist
  import subprocess
  p = subprocess.Popen("ls", stdout=subprocess.PIPE, shell=True)
  out = p.stdout.read().strip()
  newlist = out.split('\n')
  substring = ".couchID"
  for object in newlist:
    if substring in object:
      raise ValueError("couchID file exists, please remove it");
  
  # Get the options
  options = createOptionParser()
  # Check for PCL availability
  # the following loop doesn't do anything meaningful, only a confusing and inaccurate comment
  #for run in options.run:
    #if not isPCLReady(run):
    #  print "The PCL is not ready for run:",run,"... ignoring for now"
    #  print "The PCL is not ready for run:",run,"... ignoring for now"

  print options.run
  print type(options.run)
  # this type is LIST in the normal CASE, and it's also list with a single element == dictionary in the LS-filtering case. This is a problem

  # Check if it is at FNAL
  allRunsAndBlocks={}
  if not options.noSiteCheck:
    for ds in options.ds:
      allRunsAndBlocks[ds]=[]
      # FIX FIX: is below what I want ? 
      if isinstance(options.run, dict): # if run is ls-filtering, run numbers will be in lumi_list and must not be there
        print "**"
        continue
        print "** skipping run numbers"
      ## TEST TEST
      if not options.run:               # if run is not specified in the input file, leave allRunsAndBlocks empty 
        continue
      for run in options.run:
        print "inside loop PB IS HERE"
        print run
        print "inside loop PB IS HERE"
        newblocks=isAtSite( ds, int(run))
        print newblocks
        print "T or F?"
        if newblocks==False:
          print "Cannot proceed with %s in %s (no suitable blocks found)"%(ds,run)
          sys.exit(1)
        else:
          allRunsAndBlocks[ds].extend(newblocks)

  #uniquing
  for ds in allRunsAndBlocks:
    allRunsAndBlocks[ds]=list(set(allRunsAndBlocks[ds]))
    
  # Read the group of conditions from the list in the file
  confCondList= getConfCondDictionary(options)
  
  # Create the cff
  if options.HLT in ["SameAsRun","Custom"]: createHLTConfig(options)
  
  
  # Create the cfgs, both for cmsRun and WMControl  
  createCMSSWConfigs(options,confCondList,allRunsAndBlocks)

  # Print some info about final workflow  
  printInfo(options)
