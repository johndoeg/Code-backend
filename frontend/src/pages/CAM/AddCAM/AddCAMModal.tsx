import React from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../../../components/Modal';
import AddCAMCustomerModal from './AddCAMCustomerForm';

const AddCAMModal: React.FC = () => {
    const navigate = useNavigate();
    const close = () => navigate(-1);

    return (
        <Modal onClose={close} maxWidthClass="max-w-lg">
            <AddCAMCustomerModal />
        </Modal>
    );
};

export default AddCAMModal;