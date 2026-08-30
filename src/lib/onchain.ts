import type { RankedAgent, RegistryProof } from "./types";

const identityRegistryAbi = [
  {
    type: "function",
    name: "ownerOf",
    stateMutability: "view",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "owner", type: "address" }],
  },
  {
    type: "function",
    name: "tokenURI",
    stateMutability: "view",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "uri", type: "string" }],
  },
] as const;

export async function verifyRegistryProof(agent: RankedAgent): Promise<RegistryProof> {
  if (!/^\d+$/.test(agent.tokenId)) throw new Error("Invalid numeric token ID");

  const [{ createPublicClient, http, isAddressEqual }, { bsc }] = await Promise.all([
    import("viem"),
    import("viem/chains"),
  ]);
  const publicClient = createPublicClient({
    chain: bsc,
    transport: http("https://bsc-dataseed.bnbchain.org"),
  });
  const tokenId = BigInt(agent.tokenId);
  const [owner, tokenUri, blockNumber] = await Promise.all([
    publicClient.readContract({
      address: agent.contractAddress,
      abi: identityRegistryAbi,
      functionName: "ownerOf",
      args: [tokenId],
    }),
    publicClient.readContract({
      address: agent.contractAddress,
      abi: identityRegistryAbi,
      functionName: "tokenURI",
      args: [tokenId],
    }),
    publicClient.getBlockNumber(),
  ]);

  return {
    verified: isAddressEqual(owner, agent.ownerAddress),
    owner,
    tokenUri,
    blockNumber,
    checkedAt: new Date().toISOString(),
  };
}

export function bscScanTokenUrl(agent: RankedAgent): string {
  return `https://bscscan.com/token/${agent.contractAddress}?a=${encodeURIComponent(agent.tokenId)}`;
}

export function bscScanTransactionUrl(txHash: `0x${string}`): string {
  return `https://bscscan.com/tx/${txHash}`;
}
