import React, { useState, useEffect, useMemo, useRef } from 'react';
import './AdvancedQueryComposer.css';

import { getCorpusList } from './services/corpora';
import { advancedQuery, cancelQuery } from './services/query';
import LoadingIndicator from './LoadingIndicator';

const MAX_RETURNED_BLOCKS = 300;

const availableCommands = [
  { name: 'match_trees', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'match_subtrees', input: 'Dependency Tree', output: 'Dependency Tree' }, 
  { name: 'match_found_in_tree', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'match_wordlines', input: 'Word Line', output: 'Word Line' },
  { name: 'match_segments', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'change_wordlines', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'change_subtrees', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'find_paths', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'find_partial_subtrees', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'statistics', input: 'Word Line', output: 'Statistics' },
  { name: 'ngram_statistics', input: 'Word Line', output: 'Statistics' },
  { name: 'tree_ngram_statistics', input: 'Dependency Tree', output: 'Statistics' },
  { name: 'treetype_statistics', input: 'Dependency Tree', output: 'Statistics' },
  { name: 'head_dep_statistics', input: 'Dependency Tree', output: 'Statistics' },
  { name: 'count_wordlines', input: 'Word Line', output: 'Statistics' },
  { name: 'count_trees', input: 'Dependency Tree', output: 'Statistics' },
  { name: 'take_trees', input: 'Dependency Tree', output: 'Dependency Tree' },
  { name: 'underscore_fields', input: 'Word Line', output: 'Word Line' },
  { name: 'extract_fields', input: 'Word Line', output: 'Word Line' },
  { name: 'extract_sentences', input: 'Dependency Tree', output: 'Sentences' },
  { name: 'trees2conllu', input: 'Dependency Tree', output: 'CoNLLU' },
  { name: 'trees2wordlines', input: 'Dependency Tree', output: 'Word Line' },
];

const statsOrConlluCommands = new Set(
  availableCommands
    .filter(cmd => cmd.output === 'Statistics' || cmd.output === 'CoNLLU')
    .map(cmd => cmd.name)
);

const splitResultIntoBlocks = (resultText, queryLine) => {
  if (!resultText) {
    return [];
  }

  const normalizedText = typeof resultText === 'string' ? resultText : String(resultText);
  const lines = normalizedText.split(/\r?\n/);
  lines.shift(); // Remove header line
  const blocks = [];
  let currentBlock = [];

  for (const line of lines) {
    if (line.trim() === '') {
      if (currentBlock.length > 0) {
        blocks.push(currentBlock.join('\n'));
        if (blocks.length >= MAX_RETURNED_BLOCKS) {
          return blocks
        }
        currentBlock = [];
      }
      continue;
    }

    currentBlock.push(line);
  }

  if (currentBlock.length > 0) {
    blocks.push(currentBlock.join('\n'));
  }

  if (blocks.length === 1) {
    if (!queryLine?.some(line => statsOrConlluCommands.has(line.command))) {
      return lines.filter(line => line.trim() !== '');
    }
  }

  return blocks;
};

const renderBlockWithBoldMarkers = (block) => {
  if (!block || !block.includes('**')) {
    return block;
  }

  const parts = block.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, index) => (
    index % 2 === 1 ? <strong key={index}>{part}</strong> : <React.Fragment key={index}>{part}</React.Fragment>
  ));
};

const AdvancedQueryComposer =() => {
  const [corpus, setCorpus] = useState('');
  const [corpusList, setCorpusList] = useState([]);
  const [lines, setLines] = useState([{ command: '', query: ''}]);
  const [contextSize, setContextSize] = useState(0);
  const [queryResult, setQueryResult] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const abortControllerRef = useRef(null);
  const resultBlocks = useMemo(() => splitResultIntoBlocks(queryResult, lines), [queryResult, lines]);

  useEffect(() => {
  const fetchCorpora = async () => {
    try {
      const availableCorpora = await getCorpusList();
      setCorpusList(availableCorpora);
    } catch (err) {
      console.error('Error fetching corpora:', err);
    }
  };

  fetchCorpora();
}, []);

  const addLine = () => {
    setLines([...lines, { command: '', query: ''}]);
  };

  const updateLine = (index, key, value) => {
    const updated = [...lines];
    updated[index][key] = value;
    setLines(updated);
  };

  const removeLine = (index) => {
    const updated = [...lines];
    updated.splice(index, 1);
    setLines(updated);
  };

  const getInputFormat = (command) => {
    const found = availableCommands.find(c => c.name === command);
    if (found) {
      return found.input ? found.input : 'Any';
    }
    else {
      return '—';
    }
  };

  const getOutputFormat = (command) => {
    const found = availableCommands.find(c => c.name === command);
    if (found) {
      return found.output ? found.output : 'Any';
    }
    else {
      return '—';
    }
  };

  const noEmptyCommands = () => {
    return lines.every(line => line.command);
  }

  const isPipelineValid = () => {
    for (let i = 0; i < lines.length - 1; i++) {
      const currentOutput = getOutputFormat(lines[i].command);
      const nextInput = getInputFormat(lines[i + 1].command);
      if (currentOutput && nextInput && currentOutput !== nextInput) {
        return false;
      }
    }
    return true;
  };

  const handleSubmitQuery = () => {
    if (!corpus) {
      alert('Please select a corpus.');
      return;
    }
    if (lines.length === 0) {
      alert('Please add at least one command.');
      return;
    }
    if (!noEmptyCommands()) {
      alert('Please fill in all commands.');
      return;
    }
    if (!isPipelineValid()) {
      alert('Invalid pipeline: mismatched input/output formats between steps.');
      return;
    }

    setQueryResult(''); // Clear previous results
    setIsSearching(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Compose query string
    const queryString = lines.map(line => `${line.command} ${line.query}`).join(' | ');

    console.log('Submitting query:', queryString);
    advancedQuery({ corpus, query: queryString, contextSize, signal: controller.signal })
      .then(result => {
        setQueryResult(result);
      })
      .catch(error => {
        if (error.name === 'CanceledError') {
          return;
        }
        console.error('Error submitting query:', error);
        alert('The query syntax is invalid. Please modify and try again.');
      })
      .finally(() => {
        setIsSearching(false);
      });

  }

  const handleStopQuery = () => {
    abortControllerRef.current?.abort();
    cancelQuery();
    setIsSearching(false);
  }

  return (
    <div className="queryComposerDiv">
      <h2>Advanced Query Composer</h2>
      <div className="buttonRow">
        <button
          onClick={() => setLines([{ command: '', query: '' }])}
          className="resetQueryButton"
          disabled={isSearching}
        >
          Reset Query
        </button>

        <label className="contextSizeControl">
          Context size:
          <input
            type="number"
            min="0"
            step="1"
            value={contextSize}
            onChange={(e) => setContextSize(Math.max(0, Number(e.target.value) || 0))}
            className="contextSizeInput"
            disabled={isSearching}
          />
        </label>

        <button
          onClick={addLine}
          className="addLineButton"
          disabled={isSearching}
        >
          + Add Command
        </button>
      </div>

      <span className="corpusLabel">
        Corpus:
      </span>

      <select
        className="corpusDropdown"
        value={corpus}
        onChange={(e) => setCorpus(e.target.value)}
        disabled={isSearching}
      >
        <option value="">Select corpus</option>
        {corpusList.map(corpus => (
          <option key={corpus} value={corpus}>{corpus}</option>
        ))}
      </select>

      <div className="commandLine">
        {lines.map((line, index) => (
         <div key={index} className="commandLineRow">
            {/* Command Dropdown */}
            <select
              className="commandDropdown"
              value={line.command}
              onChange={(e) => updateLine(index, 'command', e.target.value)}
              disabled={isSearching}
            >
              <option value="">Select command</option>
              {availableCommands.map(cmd => (
                <option key={cmd.name} value={cmd.name}>{cmd.name}</option>
              ))}
            </select>

            {/* Argument Input */}
            <input
              type="text"
              placeholder="Query..."
              className="queryInput"
              value={line.query}
              onChange={(e) => updateLine(index, 'query', e.target.value)}
              disabled={isSearching}
            />

            {/* Input Format Label */}
            <span className="inputFormatLabel">
              Input format: <strong>{getInputFormat(line.command)}</strong>
            </span>

            {/* Output Format Label */}
            <span className="outputFormatLabel">
              Output format: <strong>{getOutputFormat(line.command)}</strong>
            </span>

            {/* Delete Button */}
            <button
              onClick={() => removeLine(index)}
              className="removeLineButton"
              disabled={isSearching}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {isSearching ? (
        <button
          className='stopQueryButton'
          onClick={handleStopQuery}
        >
          Stop Searching
        </button>
      ) : (
        <button
          className='submitQueryButton'
          onClick={handleSubmitQuery}
        >
          Submit Query
        </button>
      )}

      {isSearching && <LoadingIndicator />}

      {!corpus && (
        <p className="corpusError">
          ⚠️ Please select a corpus to run the query.
        </p>
      )}
      {!isPipelineValid() && (
        <p className="pipelineError">
          ⚠️ Invalid pipeline: mismatched input/output formats between steps.
        </p>
      )}

      {queryResult && (
        <div className="queryResult">
          <h2>Query Result:</h2>
          <div className="queryResultBlocks">
            {resultBlocks.map((block, index) => (
              <div key={index} className="queryResultBlock">
                {renderBlockWithBoldMarkers(block)}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

export default AdvancedQueryComposer;
