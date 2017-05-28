import os

import nibabel as nib
import numpy as np

import misc_io as util
from misc import CacheFunctionOutput

STANDARD_ORIENTATION = [[0, 1], [1, 1], [2, 1]]


class MultiModalFileList(object):
    def __init__(self, multi_mod_filenames):
        # list of multi-modality images filenames
        # each list element is a filename of a single-mod volume
        self.multi_mod_filenames = multi_mod_filenames

    def __call__(self):
        return self.multi_mod_filenames

    @property
    def num_time_point(self):
        if self.multi_mod_filenames is None:
            return 0
        if self.multi_mod_filenames == '':
            return 0
        return len(self.multi_mod_filenames)

    @property
    def num_modality(self):
        if self.multi_mod_filenames is None:
            return 0
        if self.multi_mod_filenames == '':
            return 0
        return len(self.multi_mod_filenames[0])


class Subject(object):
    """
    This class specifies all properties of a subject
    """

    fields = ('input_image_file',
              'target_image_file',
              'weight_map_file',
              'target_note')
    data_types = ('image_filename',
                  'image_filename',
                  'image_filename',
                  'textual_comment')

    def __init__(self, name, modality_names=None):
        self.name = name
        self.modality_names = modality_names
        self.csv_cell_dict = self._create_empty_csvcell_dict()

        self.load_reorientation = False
        self.load_resampling = False
        self.spatial_padding = None
        self.input_image_shape = None

    @classmethod
    def from_csv_row(cls, row, modality_names=None):
        new_subject = cls(name=row[0])
        csv_cell_list = [MultiModalFileList(column) if column != '' else None
                         for column in row[1:]]
        new_subject.set_all_columns(*csv_cell_list)
        if modality_names is not None:
            # check modality names consistent with subject image files
            assert(len(modality_names) == len(new_subject.column(0)()[0]))
            new_subject.modality_names = modality_names
        return new_subject

    def _create_empty_csvcell_dict(self):
        # initialise subject dict by fields
        none_tuple = tuple([None] * len(Subject.fields))
        return dict(zip(Subject.fields, none_tuple))

    def set_all_columns(self, *args):
        assert (len(args) == len(Subject.fields))
        for (i, value) in enumerate(args):
            self.set_column(i, value)

    def set_column(self, index, value):
        if value is None:
            return
        assert (isinstance(value, MultiModalFileList))
        self.csv_cell_dict[Subject.fields[index]] = value

    def column(self, index):
        if index > len(Subject.fields) - 1:
            raise ValueError(
                'subject has {} columns, attempting to access index {}'.format(
                    len(Subject.fields), index))
        return self.csv_cell_dict[Subject.fields[index]]

    @CacheFunctionOutput
    def _read_original_affine(self):
        """
        Given the list of files to load, find the original orientation
        and update the corresponding field if not done yet
        """
        img_object = self.__find_first_nibabel_object()
        util.rectify_header_sform_qform(img_object)
        return img_object.affine

    @CacheFunctionOutput
    def _read_original_pixdim(self):
        """
        Given the list of files to load, find the original spatial resolution
        and update the corresponding field if not done yet
        """
        img_object = self.__find_first_nibabel_object()
        return img_object.header.get_zooms()

    def __find_first_nibabel_object(self):
        """
        a helper function find the *first* available image from hard drive
        and return a nibabel image object. This is used to determine
        image affine/pixel size info.
        This function assumes the header data are the same across all
        input volumes for this subject
        :return: nibabel image object
        """
        input_image_files = self.column(0)()
        list_files = [item for sublist in input_image_files for item in sublist]
        for filename in list_files:
            if not filename == '' and os.path.exists(filename):
                path, name, ext = util.split_filename(filename)
                if 'nii' in ext:
                    return nib.load(filename)
        return None

    def __reorient_to_stand(self, data_5d):
        if (data_5d is None) or (data_5d.shape is ()):
            return None
        image_affine = self._read_original_affine()
        ornt_original = nib.orientations.axcodes2ornt(
            nib.aff2axcodes(image_affine))
        return util.do_reorientation(data_5d,
                                     ornt_original,
                                     STANDARD_ORIENTATION)

    def __reorient_to_original(self, data_5d):
        if (data_5d is None) or (data_5d.shape is ()):
            return None
        image_affine = self._read_original_affine()
        ornt_original = nib.orientations.axcodes2ornt(
                nib.aff2axcodes(image_affine))
        return util.do_reorientation(data_5d,
                                     STANDARD_ORIENTATION,
                                     ornt_original)

    def __resample_to_isotropic(self, data_5d, interp_order):
        if (data_5d is None) or (data_5d.shape is ()):
            return None
        image_pixdim = self._read_original_pixdim()
        return util.do_resampling(data_5d,
                                  image_pixdim,
                                  [1, 1, 1],
                                  interp_order=interp_order)

    def __resample_to_original(self, data_5d, interp_order):
        if (data_5d is None) or (data_5d.shape is ()):
            return None
        image_pixdim = self._read_original_pixdim()
        return util.do_resampling(data_5d,
                                  [1, 1, 1],
                                  image_pixdim,
                                  interp_order=interp_order)

    def __pad_volume(self, data_5d, spatial_padding):
        """
        spatial_padding should be a tuple of ((M,N), (P,Q),...)
        """
        if (data_5d is None) or (data_5d.shape is ()):
            return data_5d
        # pad the first few dims according to the length of spatial_padding
        ndim = data_5d.ndim
        if type(spatial_padding) is int:
            raise ValueError(
                "spatial_padding should be a tuple: ((M,N), (P,Q),...)")
        assert len(spatial_padding) <= ndim
        while len(spatial_padding) < ndim:
            spatial_padding = spatial_padding + ((0,0),)
        data_5d = np.pad(data_5d, spatial_padding, 'minimum')
        return data_5d


    def load_column(self,
                    index,
                    do_reorientation=False,
                    do_resampling=False,
                    interp_order=None,
                    spatial_padding=None):
        # TODO change name to read_image_as_5d
        if Subject.data_types[index] == 'textual_comment':
            return self.column(index)()[0][0]

        elif Subject.data_types[index] == 'image_filename':
            data_5d = util.csv_cell_to_volume_5d(self.column(index))
            if do_resampling and (interp_order is None):
                print("do resampling, but interpolation order is not "
                      "specified, defaulting to interp_order=3")
                interp_order = 3
            if do_resampling:
                data_5d = self.__resample_to_isotropic(data_5d, interp_order)
                self.load_resampling = True
            if do_reorientation:
                data_5d = self.__reorient_to_stand(data_5d)
                self.load_reorientation = True
            data_5d = np.nan_to_num(data_5d)
            if spatial_padding is not None:
                data_5d = self.__pad_volume(data_5d, spatial_padding)
                self.spatial_padding = spatial_padding
            if index == 0:  # if it is the target, remember the shape
                self.input_image_shape = data_5d.shape
            return {Subject.fields[index]: data_5d}
        else:
            return self.column(index)()[0][0]


    def load_columns(self,
                     index_list,
                     do_reorientation=False,
                     do_resampling=False,
                     interp_order=None,
                     spatial_padding=None):
        """
        This function load all images from file_path_list,
        returns all data (with reorientation/resampling if required)
        """

        # set default interp
        if interp_order is None:
            interp_order = [3] * len(index_list)
        if len(interp_order) < len(index_list):
            full_interp_order = [3] * len(index_list)
            full_interp_order[:len(interp_order)] = interp_order
            interp_order = full_interp_order
        output_dict = {}
        for (i, column_ind) in enumerate(index_list):
            column_dict = self.load_column(index=column_ind,
                                           do_reorientation=do_reorientation,
                                           do_resampling=do_resampling,
                                           interp_order=interp_order[i],
                                           spatial_padding=spatial_padding)
            output_dict[column_dict.keys()[0]] = column_dict.values()[0]
        return output_dict

    def __str__(self):
        out_str = []
        out_str.append('subject: {}'.format(self.name))
        for ind in range(0, len(Subject.fields)):
            csv_field = Subject.fields[ind]
            csv_cell = self.column(ind)
            if csv_cell is None:
                out_str.append('{}: None'.format(csv_field))
            else:
                out_str.append('{}: {}'.format(csv_field, csv_cell()))
        return '\n'.join(out_str)

    def modalities_dict(self):
        num_modality = self.column(0).num_modality
        if self.modality_names is not None:
            return dict(zip(self.modality_names, range(0, num_modality)))
        dict_modalities = {}
        for m in range(0, num_modality):
            name_mod = 'Modality-{}'.format(m)
            dict_modalities[name_mod] = m
        return dict_modalities

    def matrix_like_input_data_5d(self, spatial_rank, n_channels, init_value=0):
        """
        create an empty matrix with an optional initial values.
        the output is a 5d volume, with the first `spatial_rank` corresponding
        to the spatial shape of the input image, `n_channels` defines the
        number of channels, this can be
        1: segmentation map
        n: n_class probabilities or n-dim features from the network
        """
        zeros_shape = self.input_image_shape[:spatial_rank] + (n_channels,)
        while len(zeros_shape) < 5:
            zeros_shape = zeros_shape + (1,)
        return np.ones(zeros_shape) * init_value

    def save_network_output(self, data, save_path):
        if data is None:
            return
        if self.spatial_padding is not None:
            ind = util.spatial_padding_to_indexes(self.spatial_padding)
            if len(ind) == 6:  # spatial_rank == 3
                w, h, d = data.shape[:3]
                data = data[ind[0]: (w - ind[1]),
                            ind[2]: (h - ind[3]),
                            ind[4]: (d - ind[5]), :, :]
            if len(ind) == 4:  # spatial_rank == 2
                w, h = data.shape[:2]
                data = data[ind[0]: (w - ind[1]),
                            ind[2]: (h - ind[3]), :, :, :]
        if self.load_reorientation:
            data = self.__reorient_to_original(data)
        if self.load_resampling:
            data = self.__resample_to_original(data, 3)
        original_header = self.__find_first_nibabel_object()
        filename = self.name + '_niftynet_out'
        util.save_volume_5d(data, filename, save_path, original_header)
