import './LoadingIndicator.css';

const LoadingIndicator = ({ text = 'Searching...' }) => (
  <div className="loadingIndicator">
    <span className="loadingSpinner" />
    {text}
  </div>
);

export default LoadingIndicator;
