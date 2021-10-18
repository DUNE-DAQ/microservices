--------------------------------------------------------
--  File created - Monday-October-18-2021   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table RUN_REGISTRY
--------------------------------------------------------

  CREATE TABLE "RUN_REGISTRY" ("RUN_NUMBER" NUMBER, "START_TIME" TIMESTAMP (6), "STOP_TIME" TIMESTAMP (6) DEFAULT NULL, "DETECTOR_ID" VARCHAR2(40), "RUN_TYPE" VARCHAR2(40), "FILENAME" VARCHAR2(100), "CONFIGURATION" BLOB)
--------------------------------------------------------
--  DDL for Index RUN_REGISTRY_PK
--------------------------------------------------------

  CREATE UNIQUE INDEX "RUN_REGISTRY_PK" ON "RUN_REGISTRY" ("RUN_NUMBER")
--------------------------------------------------------
--  Constraints for Table RUN_REGISTRY
--------------------------------------------------------

  ALTER TABLE "RUN_REGISTRY" MODIFY ("RUN_NUMBER" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY" MODIFY ("START_TIME" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY" MODIFY ("DETECTOR_ID" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY" MODIFY ("RUN_TYPE" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY" MODIFY ("FILENAME" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY" ADD CONSTRAINT "RUN_REGISTRY_PK" PRIMARY KEY ("RUN_NUMBER") USING INDEX  ENABLE
  ALTER TABLE "RUN_REGISTRY" MODIFY ("CONFIGURATION" NOT NULL ENABLE)


