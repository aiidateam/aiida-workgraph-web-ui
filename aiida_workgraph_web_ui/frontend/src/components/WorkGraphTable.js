import React, { useState, useEffect } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import { IconButton, Tooltip } from '@mui/material';
import { PlayArrow, Pause, Delete } from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { toast, ToastContainer } from 'react-toastify';
import { FaPlay, FaPause, FaTrash } from 'react-icons/fa';
import 'react-toastify/dist/ReactToastify.css';

import WorkGraphConfirmModal from './WorkGraphModals';

function WorkGraph() {
  const [data, setData] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortModel, setSortModel] = useState([
    { field: 'pk', sort: 'desc' }, // The initial sort
  ]);

  // For the delete confirm modal
  const [showConfirmDeleteModal, setShowConfirmDeleteModal] = useState(false);
  const [bodyTextConfirmDeleteModal, setBodyTextConfirmDeleteModal] = useState(<p></p>);
  const [toDeleteItem, setToDeleteItem] = useState(null);

  // Fetch data when component mounts or search changes
  useEffect(() => {
    fetch(`http://localhost:8000/api/workgraph-data?search=${searchQuery}`)
      .then((response) => response.json())
      .then((fetched) => {
        setData(fetched);
      })
      .catch((error) => {
        console.error('Error fetching data: ', error);
      });
  }, [searchQuery]);

  // Handle server calls for the pause action
  const handlePauseClick = (item) => {
    fetch(`http://localhost:8000/api/workgraph/pause/${item.pk}`, {
      method: 'POST',
    })
      .then((response) => response.json())
      .then((respData) => {
        if (respData.message) {
          toast.success(respData.message);
          // Refresh data
          fetch(`http://localhost:8000/api/workgraph-data?search=${searchQuery}`)
            .then((response) => response.json())
            .then((fetched) => setData(fetched))
            .catch((error) => console.error('Error fetching data: ', error));
        } else {
          toast.error('Error pausing item');
        }
      })
      .catch((error) => console.error('Error pausing item: ', error));
  };

  // Handle server calls for the play action
  const handlePlayClick = (item) => {
    fetch(`http://localhost:8000/api/workgraph/play/${item.pk}`, {
      method: 'POST',
    })
      .then((response) => response.json())
      .then((respData) => {
        if (respData.message) {
          toast.success(respData.message);
          // Refresh data
          fetch(`http://localhost:8000/api/workgraph-data?search=${searchQuery}`)
            .then((response) => response.json())
            .then((fetched) => setData(fetched))
            .catch((error) => console.error('Error fetching data: ', error));
        } else {
          toast.error('Error playing item');
        }
      })
      .catch((error) => console.error('Error playing item: ', error));
  };

  // We'll run a "dry_run" to gather dependent PKs and show them in the modal
  useEffect(() => {
    if (toDeleteItem != null) {
      fetch(`http://localhost:8000/api/workgraph/delete/${toDeleteItem.pk}?dry_run=True`, {
        method: 'DELETE',
      })
        .then((response) => response.json())
        .then((dryRunResp) => {
          if (dryRunResp.deleted_nodes.length > 0) {
            // Always includes the main node
            if (dryRunResp.deleted_nodes.length > 1) {
              let toDeleteList = [...dryRunResp.deleted_nodes];
              // remove the current pk from array for display
              toDeleteList.splice(toDeleteList.indexOf(toDeleteItem.pk), 1);

              let formattedPks = toDeleteList.map((x) => ` ${x.toString()}`);
              setBodyTextConfirmDeleteModal(
                <p>
                  Are you sure you want to delete node PK&lt;{toDeleteItem.pk}&gt; and{' '}
                  {toDeleteList.length} dependent nodes?
                  <b> A deletion is irreversible.</b>
                  <br />
                  <br />
                  List of PKs that will be deleted:
                  <br /> {formattedPks.toString()}
                </p>
              );
            } else {
              // Only the node itself
              setBodyTextConfirmDeleteModal(
                <p>
                  Are you sure you want to delete node {toDeleteItem.pk}?
                  <b> A deletion is irreversible.</b>
                </p>
              );
            }
            setShowConfirmDeleteModal(true);
          } else {
            toast.error('Error deleting item.');
          }
        })
        .catch((error) => console.error('Error during dry_run for deletion:', error));
    }
  }, [toDeleteItem]);

  // Confirm deletion action in the modal
  const handleDeleteNode = (item) => {
    fetch(`http://localhost:8000/api/workgraph/delete/${item.pk}`, {
      method: 'DELETE',
    })
      .then((response) => response.json())
      .then((respData) => {
        if (respData.deleted) {
          toast.success(respData.message);
          // Refresh data
          fetch(`http://localhost:8000/api/workgraph-data?search=${searchQuery}`)
            .then((res) => res.json())
            .then((fetched) => setData(fetched))
            .catch((error) => console.error('Error fetching data: ', error));
        } else {
          toast.error('Error deleting item');
        }
      })
      .catch((error) => console.error('Error deleting item: ', error));
  };

  /**
   * DataGrid columns definition
   *
   * - field: property name from data items
   * - headerName: Column label
   * - renderCell: can be used to customize cell content (e.g., to show icons)
   * - flex or width: controls the column width
   */
  const columns = [
    {
      field: 'pk',
      headerName: 'PK',
      width: 80,
      renderCell: (params) => {
        return <Link to={`/workgraph/${params.row.pk}`}>{params.value}</Link>;
      },
      sortable: true,
    },
    {
      field: 'ctime',
      headerName: 'Created',
      width: 150,
      sortable: true,
    },
    {
      field: 'process_label',
      headerName: 'Process Label',
      width: 300,
      sortable: false, // or true if you want to allow sorting
    },
    {
      field: 'state',
      headerName: 'State',
      width: 150,
      sortable: false,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 180, // Ensure enough space for buttons
      sortable: false,
      renderCell: (params) => {
        const item = params.row;
        return (
          <>
            {/* Pause Button */}
            <Tooltip title="Pause">
              <IconButton onClick={() => handlePauseClick(item)} color="primary">
                <Pause />
              </IconButton>
            </Tooltip>
            {/* Play Button */}
            <Tooltip title="Resume">
              <IconButton onClick={() => handlePlayClick(item)} color="success">
                <PlayArrow />
              </IconButton>
            </Tooltip>
            {/* Delete Button */}
            <Tooltip title="Delete">
              <IconButton
                onClick={() => setToDeleteItem(structuredClone(item))}
                color="error"
              >
                <Delete />
              </IconButton>
            </Tooltip>
          </>
        );
      },
    },
  ];

  return (
    <div style={{ padding: '1rem' }}>
      <h2>WorkGraph</h2>

      {/* Search input */}
      <div style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search..."
          style={{ width: '300px' }}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* DataGrid container */}
      <div style={{ height: '100%', width: '100%' }}>
        <DataGrid
          rows={data}
          columns={columns}
          getRowId={(row) => row.pk} // Use pk as unique identifier
          initialState={{
            pagination: { paginationModel: { pageSize: 15} },
          }}
          pageSizeOptions={[15, 30, 50]}
          pagination
          // Sorting configuration
          sortModel={sortModel}
          onSortModelChange={(model) => {
            setSortModel(model);
          }}
        />
      </div>

      <ToastContainer autoClose={3000} />

      <WorkGraphConfirmModal
        show={showConfirmDeleteModal}
        setShow={setShowConfirmDeleteModal}
        confirmAction={() => {
          if (toDeleteItem) handleDeleteNode(toDeleteItem);
        }}
        cancelAction={() => {}}
        bodyText={bodyTextConfirmDeleteModal}
      />
    </div>
  );
}

export default WorkGraph;
