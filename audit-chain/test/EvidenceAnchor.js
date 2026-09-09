const { expect } = require('chai');
const { ethers } = require('hardhat');

describe('EvidenceAnchor', function () {
  async function deploy() {
    const [admin, writer, outsider] = await ethers.getSigners();
    const EvidenceAnchor = await ethers.getContractFactory('EvidenceAnchor');
    const anchor = await EvidenceAnchor.deploy(admin.address, writer.address);
    await anchor.waitForDeployment();
    return { anchor, admin, writer, outsider };
  }

  it('allows its designated writer to append an evidence hash and retrieve it', async function () {
    const { anchor, writer } = await deploy();
    const evidenceId = ethers.id('incident:opaque:1');
    const evidenceHash = ethers.sha256(ethers.toUtf8Bytes('canonical-evidence-v1'));

    await expect(anchor.connect(writer).recordEvidence(evidenceId, evidenceHash))
      .to.emit(anchor, 'EvidenceAnchored');

    const record = await anchor.getEvidence(evidenceId);
    expect(record.evidenceHash).to.equal(evidenceHash);
    expect(record.anchoredAt).to.be.greaterThan(0);
  });

  it('rejects an unauthorized writer and does not create a record', async function () {
    const { anchor, outsider } = await deploy();
    const evidenceId = ethers.id('incident:opaque:2');

    await expect(anchor.connect(outsider).recordEvidence(evidenceId, ethers.ZeroHash))
      .to.be.reverted;
    expect((await anchor.getEvidence(evidenceId)).evidenceHash).to.equal(ethers.ZeroHash);
  });

  it('rejects duplicate evidence IDs instead of silently overwriting the original hash', async function () {
    const { anchor, writer } = await deploy();
    const evidenceId = ethers.id('incident:opaque:3');
    await anchor.connect(writer).recordEvidence(evidenceId, ethers.id('original'));

    await expect(anchor.connect(writer).recordEvidence(evidenceId, ethers.id('replacement')))
      .to.be.revertedWithCustomError(anchor, 'EvidenceAlreadyAnchored');
    expect((await anchor.getEvidence(evidenceId)).evidenceHash).to.equal(ethers.id('original'));
  });
});
