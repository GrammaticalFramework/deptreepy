import React, { useState, useEffect, useRef } from 'react';
import './StringQueryComposer.css';

import { getCorpusList } from './services/corpora';
import { stringQuery, cancelQuery } from './services/query';
import LoadingIndicator from './LoadingIndicator';

const MAX_RETURNED_SENTENCES = 1000;

const renderBlockWithBoldMarkers = (block) => {
  if (!block || !block.includes('**')) {
    return block;
  }

  const parts = block.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, index) => (
    index % 2 === 1 ? <strong key={index}>{part}</strong> : <React.Fragment key={index}>{part}</React.Fragment>
  ));
};

const StringQueryComposer =() => {
  const [corpus, setCorpus] = useState('');
  const [corpusList, setCorpusList] = useState([]);
  const [searchString, setSearchString] = useState("");
  const [contextSize, setContextSize] = useState(0);
  const [queryResult, setQueryResult] = useState([]);
  const [searchBy, setSearchBy] = useState('Word')
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

  const isSearchStringValid = () => {
    if (!searchString || searchString.trim() === '') {
      return false;
    }
    return true;
  };

  const handleSubmitQuery = () => {
    if (!corpus) {
      alert('Please select a corpus.');
      return;
    }
    if (!isSearchStringValid()) {
      alert('Please enter a valid search string.');
      return;
    }

    setQueryResult([]); // Clear previous results
    setIsSearching(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    console.log('Submitting query:', searchString);
    stringQuery({ corpus, query: searchString, searchBy, contextSize, signal: controller.signal })
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
        alert('An error occurred while executing the query. Please check the query syntax and try again.');
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
      <h2>Search Query Composer</h2>
      <div className="buttonRow">
        <button
          onClick={() => setSearchString('')}
          className="resetQueryButton"
          disabled={isSearching}
        >
          Reset Query
        </button>

        <label className="searchByControl">
          Search by:
          <select
            className="searchByDropdown"
            value={searchBy}
            onChange={(e) => setSearchBy(e.target.value)}
            disabled={isSearching}
          >
            <option value="Word">Word</option>
            <option value="Lemma">Lemma</option>
          </select>
        </label>

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

      <div className="searchStringInputDiv">
        <input
          type="text"
          placeholder="Enter search query..."
          className="searchStringInput"
          value={searchString}
          onChange={(e) => setSearchString(e.target.value)}
          disabled={isSearching}
        />
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

export default StringQueryComposer;
