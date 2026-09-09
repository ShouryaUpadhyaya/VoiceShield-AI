ALTER TABLE "audit_records" DROP CONSTRAINT "audit_records_call_id_fkey";
ALTER TABLE "audit_records" ADD CONSTRAINT "audit_records_call_id_fkey"
  FOREIGN KEY ("call_id") REFERENCES "calls"("id") ON DELETE CASCADE ON UPDATE CASCADE;
