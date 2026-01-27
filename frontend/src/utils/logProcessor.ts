export function processLogs(logs: string): string {
  if (!logs) return '';

  // 1. Handle \r (Carriage Return) for progress bars
  const rawLines = logs.split('\n');
  const processedLines: string[] = [];
  
  for (const rawLine of rawLines) {
    // Remove potential trailing \r from \r\n split
    let line = rawLine;
    if (line.endsWith('\r')) {
        line = line.slice(0, -1);
    }

    if (line.includes('\r')) {
      const segments = line.split('\r');
      // Find the last non-empty segment
      // Iterate backwards
      let found = false;
      for (let i = segments.length - 1; i >= 0; i--) {
        if (segments[i].length > 0) {
            processedLines.push(segments[i]);
            found = true;
            break;
        }
      }
      if (!found) {
        // If all segments were empty, push empty string (or skip?)
        processedLines.push("");
      }
    } else {
      processedLines.push(line);
    }
  }

  // 2. Compaction (Downloading & TQDM)
  const finalLines: string[] = [];
  
  // Regex for "Downloading <package>" or "Downloaded <package>"
  const downloadPattern = /^(Downloading|Downloaded)\s+/;
  
  // Regex for TQDM-like progress bars
  // Examples:
  // "100%|██████████| 10/10 [00:01<00:00,  8.00it/s]"
  // " 20%|##        | ..."
  // "Downloading:  10%"
  const tqdmPattern = /^\s*\d+%\|.*\||^\s*\d+%\s+/;

  for (let i = 0; i < processedLines.length; i++) {
    const line = processedLines[i];
    
    // Check for Download pattern
    if (downloadPattern.test(line)) {
      // Look ahead for consecutive download lines
      let nextIsDownload = false;
      if (i + 1 < processedLines.length) {
        nextIsDownload = downloadPattern.test(processedLines[i + 1]);
      }
      
      if (nextIsDownload) {
        continue; // Skip this line
      }
    } 
    // Check for TQDM pattern
    else if (tqdmPattern.test(line)) {
        // Look ahead for consecutive TQDM lines
        let nextIsTqdm = false;
        if (i + 1 < processedLines.length) {
            nextIsTqdm = tqdmPattern.test(processedLines[i + 1]);
        }
        
        if (nextIsTqdm) {
            continue; // Skip this line
        }
    }
    
    finalLines.push(line);
  }

  return finalLines.join('\n');
}