--------------------------------------------------------
--  File created - Friday-October-29-2021   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table RUN_REGISTRY_CONFIGS
--------------------------------------------------------

  CREATE TABLE "RUN_REGISTRY_CONFIGS" ("RUN_NUMBER" NUMBER, "CONFIGURATION" BLOB)  LOB ("CONFIGURATION") STORE AS SECUREFILE "SYS_LOB0436808964C00002$$"(ENABLE STORAGE IN ROW CHUNK 8192 NOCACHE LOGGING  NOCOMPRESS  KEEP_DUPLICATES )
--------------------------------------------------------
--  Constraints for Table RUN_REGISTRY_CONFIGS
--------------------------------------------------------

  ALTER TABLE "RUN_REGISTRY_CONFIGS" MODIFY ("RUN_NUMBER" NOT NULL ENABLE)
  ALTER TABLE "RUN_REGISTRY_CONFIGS" MODIFY ("CONFIGURATION" NOT NULL ENABLE)
--------------------------------------------------------
--  Ref Constraints for Table RUN_REGISTRY_CONFIGS
--------------------------------------------------------

  ALTER TABLE "RUN_REGISTRY_CONFIGS" ADD CONSTRAINT "RUN_REGISTRY_CONFIGS_FK1" FOREIGN KEY ("RUN_NUMBER") REFERENCES "RUN_REGISTRY_META" ("RUN_NUMBER") ENABLE
