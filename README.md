
# Introduction

Physics-based software models use code to define an object’s real-world behaviors as it interacts with its environment. Each model can have inputs, parameters, and outputs; inputs and outputs can change over time, while parameters are set to a constant value throughout the simulation. The purpose of building a physics-based model is to simulate it and gain insight on how a design will perform. When simulating a model, the user provides information such as the start time, end time, and step size. The simulator will then calculate the result after moving through each time step (a discrete amount of time, for example 10 milliseconds).

One problem with simulation is that it is computationally expensive, therefore complex models take a long time to simulate. Cloud-based simulation can help, however, there is not yet a standardized way of simulating physics-based models in the cloud. This simulation tool can invoke multiple Python-based AWS Lambda functions to simulate a Functional Mockup Unit (FMU) model in parallel and output the results to an S3 bucket for plotting. As a result, it is possible to simulate FMUs in the cloud from anywhere with any number of inputs and parameters using this tool. It is also cost-effective since 10,000 simulations can be run for less than one dollar (USD) in AWS.

# Model simulation in AWS

This is a full guide on setting up an environment in AWS for simulating FMU models.

## Dependencies

1. Sign in to the AWS console: <https://aws.amazon.com/console/>
2. S3 is a service that lets you store files as objects within different buckets of your choosing. Navigate to the S3 Buckets service and create a new bucket called “fmpy-bucket.” This is where the .fmu files are uploaded. *Important: make sure that the bucket is private and all public access is blocked.*
3. The AWS Python SDK is called boto3. By default, it doesn’t come with any Python libraries preinstalled so we need to give it a .zip file containing the code for an open-source Python simulator called FMPy (<https://github.com/CATIA-Systems/FMPy>) and all its dependencies. Otherwise, the Lambda will not know what we’re talking about when we try to simulate a model.
4. Download the required packages (.whl files) from <https://pypi.org> and unzip them. *Note: Make sure the packages you download are compatible with Python 3.6 and are built for “many linux.”* Below are all required packages:

| Package    | Version   |
|------------|-----------|
| attr       | any       |
| attrs      | 21.4.0    |
| fmpy       | 0.3.9     |
| lxml       | any       |
| PyYAML     | 6.0       |
| requests   | 2.27.1    |
| yaml       | any       |

5. Place all the unzipped packages into a folder named “python” then zip it up and call the new archive “fmpyLayer.zip.”
6. This guide describes the process in more detail (except we want to use different packages): <https://medium.com/@shimo164/lambda-layer-to-use-numpy-and-pandas-in-aws-lambda-function-8a0e040faa18>
7. Once the .zip is on your machine, upload it to the fmpy-bucket.

### AWS Setup/Permissions

1. A Lambda function allows you to write and run code without needing to build a server. Go to Services → Lambda and create a function. *Note: the function cannot be renamed after it’s created.*
2. Choose “Author from scratch” and then Runtime → Python 3.6, and Architecture → x86 64. The rest can be left at the default settings. *Note: I could only get this to work with Python 3.6, otherwise it would throw an error about lxml and etree when importing fmpy.*
3. Next, we need to give the Lambda permissions to read/write to the S3 buckets. Open your Lambda then go to the Configuration → Permissions tab. Note the name of the execution role it uses.
4. Go to Services → IAM. Go to Roles then find the execution role from step 3. Click on Add Permissions. In the new screen, search for “S3” in the list and add the role called “AmazonS3FullAccess.”
5. Now that the required S3 permissions are set, we want to give the Lambda access to the FMPy library by creating a Layer. Open the hamburger menu and click Layers under Additional Resources. Create a new Layer called “fmpy”. Choose “Upload a file from Amazon S3”. In a new browser tab, go back to the S3 Buckets page, select the fmpyLayer.zip file in the fmpybucket, and click “Copy URL.” Paste this URL into the Layers page in the S3 link URL section, then choose Python 3.6 and x86 64 again, then click Create.
6. We need to tell the Lambda to use the Layer we just created. Go to Additional Resources → Layers. There is one more dependency we need: numpy. From my testing, trying to add it through a custom layer will cause this error described in the following link. Fortunately, we can get around this by adding the SciPy layer already provided by AWS. Check: <https://github.com/numpy/numpy/issues/14532>. In the Lambda function, scroll down to Layers, then click Add a layer. Pick “AWS layers” for Layer source then find the Python36-SciPy layer (pick the latest version). Click Add.
7. Now configure a test event for the Lambda. Follow the guide below to setup AWS command line (CLI) access for your machine: <https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html>
8. The last thing to do is add the code to the Lambda (simulateFMU.py) and use the Python notebook (InvokeLambdaSimulateFMU.ipynb) to start simulating!
<https://github.com/stpilks99/simulate-FMU-Lambda.git>
