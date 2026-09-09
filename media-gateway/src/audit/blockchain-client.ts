import { Contract, JsonRpcProvider, Wallet, keccak256, toUtf8Bytes } from 'ethers';

const ABI = [
  'function recordEvidence(bytes32 evidenceId, bytes32 evidenceHash)',
  'function getEvidence(bytes32 evidenceId) view returns (tuple(bytes32 evidenceHash,uint64 anchoredAt))',
] as const;

export interface BlockchainProof {
  transactionHash: string;
  blockNumber: number;
  network: string;
  contractAddress: string;
  anchoredAt: Date;
}

export class EvmEvidenceClient {
  readonly enabled: boolean;
  private readonly provider?: JsonRpcProvider;
  private readonly contract?: Contract;
  private readonly networkName: string;
  private readonly localSignerIndex: number;

  constructor(config = process.env) {
    this.enabled = config.BLOCKCHAIN_ENABLED === 'true';
    this.networkName = config.BLOCKCHAIN_NETWORK ?? 'VoiceShield Local Chain';
    this.localSignerIndex = Number(config.BLOCKCHAIN_LOCAL_SIGNER_INDEX ?? '0');
    if (!this.enabled) return;
    const rpcUrl = config.BLOCKCHAIN_RPC_URL;
    const privateKey = config.BLOCKCHAIN_PRIVATE_KEY;
    const contractAddress = config.BLOCKCHAIN_CONTRACT_ADDRESS;
    if (!rpcUrl || !contractAddress || (!privateKey && config.BLOCKCHAIN_LOCAL_UNSAFE_RPC_SIGNER !== 'true')) {
      throw new Error('Blockchain is enabled but RPC URL, contract address, or a server-side signer is missing');
    }
    this.provider = new JsonRpcProvider(rpcUrl);
    this.contract = new Contract(contractAddress, ABI, privateKey ? new Wallet(privateKey, this.provider) : this.provider);
  }

  static evidenceId(value: string): string {
    return keccak256(toUtf8Bytes(`voiceshield.audit.v1:${value}`));
  }

  async anchor(evidenceId: string, evidenceHash: string): Promise<BlockchainProof> {
    if (!this.enabled || !this.contract || !this.provider) throw new Error('Blockchain anchoring is disabled');
    const signer = await this.provider.getSigner(this.localSignerIndex); // Development-only unlocked Hardhat account; production uses BLOCKCHAIN_PRIVATE_KEY.
    const writable = this.contract.connect(signer) as any;
    const tx = await writable.recordEvidence(EvmEvidenceClient.evidenceId(evidenceId), `0x${evidenceHash}`);
    const receipt = await tx.wait(1);
    if (!receipt) throw new Error('Transaction was not mined');
    const block = await this.provider.getBlock(receipt.blockNumber);
    return { transactionHash: tx.hash, blockNumber: receipt.blockNumber, network: this.networkName, contractAddress: await this.contract.getAddress(), anchoredAt: new Date(Number(block?.timestamp ?? 0) * 1000) };
  }

  async get(evidenceId: string): Promise<{ evidenceHash: string; anchoredAt: Date } | null> {
    if (!this.enabled || !this.contract) return null;
    const evidence = await this.contract.getEvidence(EvmEvidenceClient.evidenceId(evidenceId));
    if (evidence.evidenceHash === `0x${'0'.repeat(64)}`) return null;
    return { evidenceHash: evidence.evidenceHash.slice(2).toLowerCase(), anchoredAt: new Date(Number(evidence.anchoredAt) * 1000) };
  }
}
