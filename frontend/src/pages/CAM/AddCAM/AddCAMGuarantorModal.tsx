import React from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../../../components/Modal';
import AddCAMGuarantorForm from './AddCAMGuarantorForm';

const AddCAMGuarantorModal: React.FC = () => {
    const navigate = useNavigate();
    const close = () => navigate(-1);

    return (
        <Modal onClose={close} maxWidthClass="max-w-lg">
            <AddCAMGuarantorForm />
        </Modal>
    );
};

export default AddCAMGuarantorModal;