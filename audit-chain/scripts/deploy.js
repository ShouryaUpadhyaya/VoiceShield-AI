const hre = require('hardhat');
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const [admin, writer] = await hre.ethers.getSigners();
  const EvidenceAnchor = await hre.ethers.getContractFactory('EvidenceAnchor');
  const anchor = await EvidenceAnchor.deploy(admin.address, writer.address);
  await anchor.waitForDeployment();
  const network = await hre.ethers.provider.getNetwork();
  const deployment = {
    chainId: Number(network.chainId),
    network: hre.network.name,
    contractAddress: await anchor.getAddress(),
    writerAddress: writer.address,
  };
  fs.writeFileSync(path.join(__dirname, '..', 'deployment.local.json'), `${JSON.stringify(deployment, null, 2)}\n`);
  console.log(JSON.stringify(deployment));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
