--------------------------------------------------------
--  File created - Monday-September-27-2021   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table RUN_NUMBER
--------------------------------------------------------

  CREATE TABLE "RUN_NUMBER" ("RN" NUMBER, "START_TIME" TIMESTAMP (6), "FLAG" NUMBER(1,0) DEFAULT 0, "STOP_TIME" TIMESTAMP (6) DEFAULT CURRENT_TIMESTAMP)
--------------------------------------------------------
--  DDL for Index RUN_NUMBER_PK
--------------------------------------------------------

  CREATE UNIQUE INDEX "RUN_NUMBER_PK" ON "RUN_NUMBER" ("RN")
--------------------------------------------------------
--  Constraints for Table RUN_NUMBER
--------------------------------------------------------

  ALTER TABLE "RUN_NUMBER" MODIFY ("RN" NOT NULL ENABLE)
  ALTER TABLE "RUN_NUMBER" MODIFY ("START_TIME" NOT NULL ENABLE)
  ALTER TABLE "RUN_NUMBER" ADD CONSTRAINT "RUN_NUMBER_PK" PRIMARY KEY ("RN") USING INDEX  ENABLE
  ALTER TABLE "RUN_NUMBER" MODIFY ("FLAG" NOT NULL ENABLE)
  ALTER TABLE "RUN_NUMBER" MODIFY ("STOP_TIME" NOT NULL ENABLE)

