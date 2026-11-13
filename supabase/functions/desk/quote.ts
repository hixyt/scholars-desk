// The same proof test as quote_in_abstract() in verify.py, so the website's claim checker
// and the morning digest judge quotes by one rule.
//
// A quote counts only if at least 80% of its words match the abstract in runs of 3 or more
// words in a row, every number in it appears in the abstract exactly, and it has at least
// 4 words. Case and punctuation are ignored.

export function words(text: string): string[] {
  return (text || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().split(" ").filter(Boolean);
}

type Block = [number, number, number]; // start in a, start in b, length

// Python's difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks(), for word lists.
export function matchingBlocks(a: string[], b: string[]): Block[] {
  const b2j = new Map<string, number[]>();
  b.forEach((w, j) => {
    const list = b2j.get(w);
    if (list) list.push(j);
    else b2j.set(w, [j]);
  });

  const longest = (alo: number, ahi: number, blo: number, bhi: number): Block => {
    let besti = alo, bestj = blo, bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const next = new Map<number, number>();
      for (const j of b2j.get(a[i]) || []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) || 0) + 1;
        next.set(j, k);
        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
      j2len = next;
    }
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti--; bestj--; bestsize++;
    }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) {
      bestsize++;
    }
    return [besti, bestj, bestsize];
  };

  const found: Block[] = [];
  const stack: [number, number, number, number][] = [[0, a.length, 0, b.length]];
  while (stack.length) {
    const [alo, ahi, blo, bhi] = stack.pop()!;
    const [i, j, k] = longest(alo, ahi, blo, bhi);
    if (k) {
      found.push([i, j, k]);
      if (alo < i && blo < j) stack.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) stack.push([i + k, ahi, j + k, bhi]);
    }
  }
  found.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]);

  const out: Block[] = [];
  let [i1, j1, k1] = [0, 0, 0];
  for (const [i2, j2, k2] of found) {
    if (i1 + k1 === i2 && j1 + k1 === j2) {
      k1 += k2;
    } else {
      if (k1) out.push([i1, j1, k1]);
      [i1, j1, k1] = [i2, j2, k2];
    }
  }
  if (k1) out.push([i1, j1, k1]);
  out.push([a.length, b.length, 0]);
  return out;
}

export function quoteInAbstract(quote: string, abstract: string): boolean {
  const q = words(quote), a = words(abstract);
  if (q.length < 4) return false; // a quote of 1 to 3 words proves nothing
  const inAbstract = new Set(a);
  if (q.some((w) => /^\d+$/.test(w) && !inAbstract.has(w))) return false;
  const matched = matchingBlocks(q, a).filter(([, , size]) => size >= 3).reduce((sum, [, , size]) => sum + size, 0);
  return matched / q.length >= 0.8;
}

// Numbers in a claim that the abstract never mentions ("10x", "95%" when the abstract says 60%).
export function missingNumbers(claim: string, abstract: string): string[] {
  const inAbstract = new Set(words(abstract));
  return [...new Set(words(claim).filter((w) => /\d/.test(w) && !inAbstract.has(w)))];
}
