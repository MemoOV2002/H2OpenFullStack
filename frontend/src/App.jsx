import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Readings from './pages/Readings';
import Status from './pages/Status';
import History from './pages/History';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Readings />} />
          <Route path="/status" element={<Status />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
