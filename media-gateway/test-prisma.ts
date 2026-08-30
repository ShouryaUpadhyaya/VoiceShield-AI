import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
  const call = await prisma.calls.findUnique({
    where: { id: "f16204e5-f4cb-4d62-9874-df3e7388393d" },
    include: { audio_streams: true, recordings: true }
  });
  console.log(JSON.stringify(call, null, 2));
}

main().catch(console.error).finally(() => prisma.$disconnect());
