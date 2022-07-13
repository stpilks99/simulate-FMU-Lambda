import json
import boto3
import os
import numpy as np
import datetime
import time as pytime

import fmpy
from fmpy import *
from fmpy.fmi2 import FMU2Slave

def lambda_handler(event, context):
    start_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    runtime_start = pytime.time()
    
    # to grab FMU file from S3
    s3_client = boto3.client("s3")
    S3_BUCKET = 'fmpy-bucket'
    S3_RESULT_BUCKET = 'simulate-fmu-results-bucket'
    
    # input data is available to the lambda via the events dictionary
    # provided by the jupyter notebook
    try:
        parameter_object_key = event['parameter_file']
        input_object_key = event['input_file']
        fmu_filename = event['fmu_file']
        start_time = event['start_time']
        end_time = event['end_time']
        step_size = event['step_size']
        # only required if using a threshold
        #threshold = event['threshold'] 
        index = event['index']
    except: #key error
        return{
            'body': json.dumps("Error: event data missing required information (parameter_file, input_file, fmu_file, start_time, end_time, step_size, threshold, index).")

        }
    
    parameter_file_path = '/tmp/{}'.format(os.path.basename(parameter_object_key))
    input_file_path = '/tmp/{}'.format(os.path.basename(input_object_key))
    
    # download parameter file from S3
    try:
        s3_client.download_file(Bucket=S3_BUCKET, Key=parameter_object_key, Filename=parameter_file_path)
    except:
        return {
            'body': json.dumps("Error: could not find <FMUModelName>_pSets.json in the s3 bucket.")
        }
        
    # download inputs file
    try:
        s3_client.download_file(Bucket=S3_BUCKET, Key=input_object_key, Filename=input_file_path)
    except:
        return {
            'body': json.dumps("Error: could not find <FMUModelName>_iSet.json in the s3 bucket.")
        }
        
    # open and read json 
    print('Reading pSets.json...')
    with open(parameter_file_path, 'r') as j:
        parameter_json_content = json.loads(j.read())

    print('Reading iSet.json...')
    with open(input_file_path, 'r') as j:
        input_json_content = json.loads(j.read())
    
    # get the file from S3 bucket
    # we don't want to read the stuff, just grab the archive itself
    # find a way to bring the whole archive in
    # lambda just needs to know where the file
    # fmu will be saved in the ephemeral /tmp/ folder since that's what the lambda can write to
    fmu_file_path = '/tmp/{}'.format(os.path.basename(fmu_filename))
    
    # download FMU model from S3 and put it in the /tmp directory
    try:
        s3_client.download_file(Bucket=S3_BUCKET, Key=fmu_filename, Filename=fmu_file_path)
    except:
        return {
            'body': json.dumps("Error: could not find the specified FMU file in the s3 bucket.")
        }
        
    # print out info about the fmu
    dump(fmu_file_path)
    model_description = read_model_description(fmu_file_path)
    
    # print out all model parameters and the value references for each variable
    vrs = {}
    for variable in model_description.modelVariables:
        vrs[variable.name] = variable.valueReference
    print('All parameters:', vrs)
    
    # can take parameters dictionary, look for it in the json file
    # for every parameter in parameter dictionary
    # if we don't set all the parameters, don't run
    # print out error with missing parameters
    
    # looping through each dictionary element to check which inputs and parameters were given, then compare to the parameters gathered from the model
    vr_inputs = []
    input_names = []
    input_values = []
    parameter_names = []
    parameter_values = []
    output_names = []
    vr_parameters = []
    vr_outputs = []
    
    # get the value references for the variables we want to get/set, use the json files
    for key in parameter_json_content:
        if key in vrs:
            print('Found a parameter with name:', key)
            parameter_values.append(parameter_json_content[key])
            vr_parameters.append(vrs[key])
            parameter_names.append(key)
            
    # inputs
    for key in input_json_content:
        if key in vrs:
            print('Found an input with name:', key)
            input_values.append(input_json_content[key])
            vr_inputs.append(vrs[key])
            input_names.append(key)
            
    # getting outputs from the model description
    vr_outputs = []
    # https://github.com/CATIA-Systems/FMPy/blob/b76dfc85c9308a18f152fc80059cc97b8a86324b/fmpy/util.py#L664
    for v in model_description.modelVariables:
        if v.causality == 'output':
            vr_outputs.append(vrs[v.name])
            output_names.append(v.name)
    
    # fmu file is stored in /tmp
    print('FMU filename:', fmu_filename)
    
    # unzip the .fmu archive
    unzipdir = extract(fmu_file_path)
    
    # check which FMU type
    # logic: if it's not cosimulation, then it must be modelexchange
    try:
        fmu = FMU2Slave(guid=model_description.guid,
            unzipDirectory=unzipdir,
            modelIdentifier=model_description.coSimulation.modelIdentifier,
            instanceName='instance1')
    except AttributeError:
        fmu = FMU2Slave(guid=model_description.guid,
            unzipDirectory=unzipdir,
            modelIdentifier=model_description.modelExchange.modelIdentifier,
            instanceName='instance1')
    except Exception:
        return {
            'body': json.dumps("Error: could not initialize the FMU due to missing Linux binaries. Please see: https://github.com/CATIA-Systems/FMPy/issues/330")
        }
        
    # nonetype error
    # means that the wrong fmu type was selected for the model
    
    # start timing the simulation
    
    # run simulation
    print("Done")
        
    # needs to be done in a clever way
    print("Initializing simulation...")
    # reset fmu
    fmu.instantiate()
    fmu.setupExperiment(startTime=start_time)
    fmu.enterInitializationMode()
    fmu.exitInitializationMode()
    print("Done")
    print("Running simulation...")
    time = start_time
    rows = []  # list to record the results
    
    # set initial value for outputs
    #fmu.setReal(vr_outputs, )
    
    # simulation loop
    while time < end_time:
        # NOTE: the FMU.get*() and FMU.set*() functions take lists of
        # value references as arguments and return lists of values
        #----------------- tweak the parameters here -----------------------
        # example: input is 0 until 0.9 seconds then becomes input_value
        # https://github.com/CATIA-Systems/FMPy/blob/b76dfc85c9308a18f152fc80059cc97b8a86324b/fmpy/fmi2.py#L314
        try:
            # set parameters
            fmu.setReal(vr_parameters, parameter_values)
            # set inputs
            fmu.setReal(vr_inputs, input_values)
        except:
            return{
                "body": "Error: failed to set custom inputs. This model may not allow parameters/inputs to be set."
            }
            # to catch "fmi2SetReal failed with status 3" error
    
        # perform one step in the simulation
        fmu.doStep(currentCommunicationPoint=time, communicationStepSize=step_size)
    
        # advance the time
        time += step_size
    
        # get the new values for 'inputs' and 'outputs' after advancing one step
        inputs  = fmu.getReal(vr_inputs)
        outputs = fmu.getReal(vr_outputs)
        
        # append the new data
        new_data = []
        new_data.append(time)
        if len(inputs) > 0:
            for i in inputs:
                new_data.append(i)
        # couldn't use zip because inputs and outputs not might be the same length and zip will only iterate through the smallest array
        # couldn't use concatenate because float is not iterable
        for i in parameter_values:
            new_data.append(i)
        for i in outputs:
            new_data.append(i)
        
        # append to rows for the output file
        rows.append(new_data)
        
        #### end of simulation loop ####
        
    # end simulation
    fmu.terminate()
    fmu.freeInstance()  
    print("Done")
    
    # defining a folder to put all the csv files
    current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    result_bucket_folder = fmu_filename + str(current_time) + "_Run" + str(index)
    result_filename = fmu_filename + "_" + current_time + "_.csv"
    result_filepath = '/tmp/' + result_filename 
    
    # print a report showing total runtime, start date, end date, RTF (ratio of real time to simulated time)
    end_date = datetime.datetime.now()
    runtime = pytime.time() - runtime_start
    simulation_report_name = fmu_filename + str(start_date) + '.txt'
    simulation_report_path = '/tmp/' + simulation_report_name
    # RTF = simulated time / real time
    rtf = (end_time - start_time) / (runtime)
    with open(simulation_report_path, 'w') as f:
        f.write('Simulation Results\n')
        f.write('FMU file: ' + fmu_filename + '\n')
        f.write('Start date: ' + str(start_date) + '\n')
        f.write('End date: ' + str(end_date) + '\n')
        f.write('Simulation start time: ' + str(start_time) + '\n')
        f.write('Simulation end time: ' + str(end_time) + '\n')
        f.write('Total runtime: ' + str(runtime) + '\n')
        f.write('Real time factor (simulated time / real time): ' + str(rtf) + '\n')
        
    # upload the report file to S3
    s3_client.upload_file(simulation_report_path, S3_RESULT_BUCKET, simulation_report_name)

    # creating a header for the CSV file
    csv_header = "time,"
    for i in input_names:
        csv_header = csv_header + i + ","
    for i in parameter_names:
        csv_header = csv_header + i + ","
    for i in output_names:
        csv_header = csv_header + i + ","
    csv_header = csv_header.rstrip(",")
        
    # writing to file
    print('Writing results to file...')
    # comments = "" argument is so there's no # character at the beginning of the file
    np.savetxt(result_filepath, rows, delimiter=",", comments = "", fmt="%s", header = csv_header)
    
        
    # send to S3 bucket 
    # (path to file you're uploading, bucket name, name of object in bucket)
    print('Uploading to S3 bucket', S3_RESULT_BUCKET,'...')
    s3_client.upload_file(result_filepath, S3_RESULT_BUCKET, result_filename)

    return {
        'runtime': str(runtime) + ' second(s)',
        'statusCode': 200,
        'body': json.dumps('Ran successfully!')
    }
    
    # generic lambda that takes in the FMU with corresponding parameter set
    # simulate it if the parameters are valid
    # another lambda function that could collect all the results
    # use pandas dataframe
    # then download to local machine to do the plotting
    # write a script that looks in the results bucket and collect specified results (per day, etc.)
    # then can download pandas dataframe files
    # to/from json
    # look for readily available models, note which ones fail (binraries error, etc..)
    # need to cut simulink solver
    # only works on Python 3.6
    # note these things in the readme