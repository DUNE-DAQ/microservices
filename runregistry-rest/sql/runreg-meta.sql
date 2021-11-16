--------------------------------------------------------
--  File created - Friday-October-29-2021   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table RUN_REGISTRY_META
--------------------------------------------------------

  CREATE TABLE "RUN_REGISTRY_META" ("RUN_NUMBER" NUMBER, "START_TIME" TIMESTAMP (6), "STOP_TIME" TIMESTAMP (6), "DETECTOR_ID" VARCHAR2(40), "RUN_TYPE" VARCHAR2(40), "FILENAME" VARCHAR2(100), "SOFTWARE_VERSION" VARCHAR2(40))
--------------------------------------------------------
--  DDL for Index RUN_REGISTRY_META_PK
--------------------------------------------------------

  CREATE UNIQUE INDEX "RUN_REGISTRY_META_PK" ON "RUN_REGISTRY_META" ("RUN_NUMBER")
--------------------------------------------------------
--  Constraints for Table RUN_REGISTRY_META
--------------------------------------------------------

  ALTER TABLE "RUN_REGISTRY_META" ADD CONSTRAINT "RUN_REGISTRY_META_PK" PRIMARY KEY ("RUN_NUMBER") USING INDEX  ENABLE
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("RUN_NUMBER" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("START_TIME" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("DETECTOR_ID" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("RUN_TYPE" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("FILENAME" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_META" MODIFY ("SOFTWARE_VERSION" NOT NULL ENABLE)
