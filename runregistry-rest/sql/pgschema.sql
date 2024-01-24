CREATE TABLE RUN_REGISTRY_META(
    RUN_NUMBER INT PRIMARY KEY NOT NULL,
    START_TIME TIMESTAMP (6) NOT NULL,
    STOP_TIME TIMESTAMP (6),
    DETECTOR_ID VARCHAR (40) NOT NULL,
    RUN_TYPE VARCHAR (40) NOT NULL,
    FILENAME VARCHAR (100) NOT NULL,
    SOFTWARE_VERSION VARCHAR (40)
); 

CREATE UNIQUE INDEX RUN_REGISTRY_META_PK ON RUN_REGISTRY_META (RUN_NUMBER);

CREATE TABLE RUN_REGISTRY_CONFIGS(
  RUN_NUMBER INT NOT NULL,   
  CONFIGURATION BYTEA NOT NULL,
  CONSTRAINT RUN_REGISTRY_CONFIGS_FK1
    FOREIGN KEY(RUN_NUMBER)
       REFERENCES RUN_REGISTRY_META(RUN_NUMBER)
);
