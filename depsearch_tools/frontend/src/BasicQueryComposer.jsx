import React, { useState, useEffect, useRef } from 'react';
import './BasicQueryComposer.css';

import { getCorpusList } from './services/corpora';
import { basicQuery, cancelQuery } from './services/query';
import LoadingIndicator from './LoadingIndicator';

const MAX_RETURNED_SENTENCES = 1000;

const availableCommands = [
  { name: 'match_trees', input:'Dependency Tree', output: 'Dependency Tree' },
  { name: 'match_subtrees', input:'Dependency Tree', output: 'Dependency Tree' }, 
  { name: 'match_found_in_tree', input:'Dependency Tree', output: 'Dependency Tree' },
];

const renderBlockWithBoldMarkers = (block) => {
  if (!block || !block.includes('**')) {
    return block;
  }

  const parts = block.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, index) => (
    index % 2 === 1 ? <strong key={index}>{part}</strong> : <React.Fragment key={index}>{part}</React.Fragment>
  ));
};

const BasicQueryComposer =() => {
  const [corpus, setCorpus] = useState('');
  const [corpusList, setCorpusList] = useState([]);
  const [lines, setLines] = useState([{ command: '', query: ''}]);
  const [contextSize, setContextSize] = useState(0);
  const [queryResult, setQueryResult] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const abortControllerRef = useRef(null);

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

  const noEmptyFields = () => {
    return lines.every(line => line.command && line.query);
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
    if (!noEmptyFields()) {
      alert('Please fill in all command and query fields.');
      return;
    }
    if (!isPipelineValid()) {
      alert('Invalid pipeline: mismatched input/output formats between steps.');
      return;
    }

    setQueryResult([]); // Clear previous results
    setIsSearching(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Compose query string
    const queryString = lines.map(line => `${line.command} ${line.query}`).join(' | ');

    console.log('Submitting query:', queryString);
    basicQuery({ corpus, query: queryString, contextSize, signal: controller.signal })
      .then(result => {
        setQueryResult(result.slice(0, MAX_RETURNED_SENTENCES));
        if (result.length === 0) {
          alert('No results found for the given query.');
        }
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
      <h2>Basic Query Composer</h2>
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

      {queryResult.length > 0 && (
        <div className="queryResultTable">
          <h2>Query Result</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Sentence</th>
              </tr>
            </thead>
            <tbody>
              {queryResult.map((sentence, index) => (
                <tr key={index}>
                  <td>{index + 1}</td>
                  <td>{renderBlockWithBoldMarkers(sentence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}

export default BasicQueryComposer;
