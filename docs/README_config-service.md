# Configuration

The Configuration services/scripts consist of two main applications: the main configuration service and the archiver.
One can use the service exclusively, without the need of running the archiver.

## MongoDB Service

The service application is responsible for DAQling configuration retrieval and storing from/to a MongoDB database.

### Dependencies

Apply the following Ansible roles with a playbook:

    install-webdeps
    install-mongodb

### Running the service

    python3 conf-service.py

The service is located at `scripts/Configuration/`.

The `service-config.json` configuration file is at `scripts/Configuration/config`.

### Uploading a configuration collection

The `uploadConfig` tool, allows to specify the name of a directory in `configs/` whose content will be uploaded to the configuration database as a collection.

Uploading a configuration folder with the same name, will automatically bump the version of the uploaded document.

 If the directory name contains a trailing "_vN" (version N) string, the latter will be stripped and the configuration files will be added to the collection with the stripped folder name, tagging it with the next free version number in that collection.

### Checking out a configuration

The `checkoutConfig` tool, allows to get a list of available configuration collections:

```
python3 checkoutConfig.py list
```

Checkout locally the latest version of a configuration collection name:

```
python3 checkoutConfig.py <config_name>
```

Checkout a specific version of a configuration collection name:

```
python3 checkoutConfig.py <config_name> <version>
```

The checked out folder, will have a trailing `_vN` string reporting the version of the configuration.

## Archiver (experimental)

The service is responsible for periodic lookup for new configurations in a MongoDB configuration database.
If newer configurations were found, than the last inserted configuration in the Oracle database, the service
reads the new ones and inserts them into the Oracle archives.

### Running the archiver

The archiver is meant to be registered as a supervised process, with the following parameters:

    [group:configuration]
    programs=archiver
    
    [program:archiver]
    command=/<python3.6-path>/python3.6 /<daqling-path>/scripts/Configuration/archiver.py --config /<archiver-config-path>/<config>
    numprocs=1
    autostart=true
    autorestart=true
    stopsignal=QUIT
    stopwaitsecs=10
