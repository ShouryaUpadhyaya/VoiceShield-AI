// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from '@openzeppelin/contracts/access/AccessControl.sol';

/**
 * Append-only commitments for off-chain VoiceShield incident evidence.
 * This contract never accepts audio, transcripts, caller identities, or scores.
 */
contract EvidenceAnchor is AccessControl {
    bytes32 public constant WRITER_ROLE = keccak256('WRITER_ROLE');

    struct Evidence {
        bytes32 evidenceHash;
        uint64 anchoredAt;
    }

    mapping(bytes32 evidenceId => Evidence) private evidenceById;

    error EvidenceAlreadyAnchored(bytes32 evidenceId);
    error InvalidEvidenceHash();

    event EvidenceAnchored(
        bytes32 indexed evidenceId,
        bytes32 indexed evidenceHash,
        uint64 anchoredAt
    );

    constructor(address admin, address writer) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(WRITER_ROLE, writer);
    }

    function recordEvidence(bytes32 evidenceId, bytes32 evidenceHash) external onlyRole(WRITER_ROLE) {
        if (evidenceHash == bytes32(0)) revert InvalidEvidenceHash();
        if (evidenceById[evidenceId].evidenceHash != bytes32(0)) {
            revert EvidenceAlreadyAnchored(evidenceId);
        }

        uint64 anchoredAt = uint64(block.timestamp);
        evidenceById[evidenceId] = Evidence({evidenceHash: evidenceHash, anchoredAt: anchoredAt});
        emit EvidenceAnchored(evidenceId, evidenceHash, anchoredAt);
    }

    function getEvidence(bytes32 evidenceId) external view returns (Evidence memory) {
        return evidenceById[evidenceId];
    }
}
