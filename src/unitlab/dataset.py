import asyncio
import copy
import itertools
import json
import logging
import os
from collections import defaultdict

import aiofiles
import aiohttp

from .exceptions import SubscriptionError

logger = logging.getLogger(__name__)


class COCO:
    def __init__(self, annotation_type, annotation_path, data_path):
        """
        :param annotation_type (str): one of ['img_bbox', 'img_semantic_segmentation', 'img_polygon', 'img_keypoints']
        :param annotation_path (str): location of annotation file
        :param data_path (str): directory containing the images
        :return:
        """
        self.annotation_type = annotation_type
        self.annotation_path = annotation_path
        self.data_path = data_path
        self.anns, self.cats, self.imgs = dict(), dict(), dict()
        self.imgToAnns, self.catToImgs = defaultdict(list), defaultdict(list)
        self._load_dataset()

    @staticmethod
    def _is_array_like(obj):
        return hasattr(obj, "__iter__") and hasattr(obj, "__len__")

    def _validate(self):
        if not os.path.isdir(self.data_path):
            raise ValueError(
                "Data path '{}' does not exist or is not a directory".format(
                    self.data_path
                )
            )
        for required_key in ["images", "annotations", "categories"]:
            if required_key not in self.dataset.keys():
                raise KeyError(
                    "Required key '{}' not found in the COCO dataset".format(
                        required_key
                    )
                )
            if len(self.dataset[required_key]) == 0:
                raise ValueError(
                    "Required key '{}' does not contain values".format(required_key)
                )

    def _load_dataset(self):
        with open(self.annotation_path, "r") as f:
            self.dataset = json.load(f)
        self._validate()
        self.createIndex()

    def createIndex(self):
        anns, cats, imgs = {}, {}, {}
        imgToAnns, catToImgs = defaultdict(list), defaultdict(list)
        for ann in self.dataset["annotations"]:
            imgToAnns[ann["image_id"]].append(ann)
            anns[ann["id"]] = ann

        for img in self.dataset["images"]:
            imgs[img["id"]] = img

        for cat in self.dataset["categories"]:
            cats[cat["id"]] = cat

        for ann in self.dataset["annotations"]:
            catToImgs[ann["category_id"]].append(ann["image_id"])

        # create class members
        self.anns = anns
        self.imgToAnns = imgToAnns
        self.catToImgs = catToImgs
        self.imgs = imgs
        self.cats = cats
        self.categories = sorted(
            copy.deepcopy(self.loadCats(self.getCatIds())), key=lambda x: x["id"]
        )
        self.classes = [cat["name"] for cat in self.categories]
        self.original_category_referecences = dict()
        for i, category in enumerate(self.categories):
            self.original_category_referecences[category["id"]] = i
            category["id"] = i

    def getAnnIds(self, imgIds=[], catIds=[], areaRng=[], iscrowd=None):
        """
        Get ann ids that satisfy given filter conditions. default skips that filter
        :param imgIds  (int array)     : get anns for given imgs
               catIds  (int array)     : get anns for given cats
               areaRng (float array)   : get anns for given area range (e.g. [0 inf])
               iscrowd (boolean)       : get anns for given crowd label (False or True)
        :return: ids (int array)       : integer array of ann ids
        """
        imgIds = imgIds if self._is_array_like(imgIds) else [imgIds]
        catIds = catIds if self._is_array_like(catIds) else [catIds]

        if len(imgIds) == len(catIds) == len(areaRng) == 0:
            anns = self.dataset["annotations"]
        else:
            if not len(imgIds) == 0:
                lists = [
                    self.imgToAnns[imgId] for imgId in imgIds if imgId in self.imgToAnns
                ]
                anns = list(itertools.chain.from_iterable(lists))
            else:
                anns = self.dataset["annotations"]
            anns = (
                anns
                if len(catIds) == 0
                else [ann for ann in anns if ann["category_id"] in catIds]
            )
            anns = (
                anns
                if len(areaRng) == 0
                else [
                    ann
                    for ann in anns
                    if ann["area"] > areaRng[0] and ann["area"] < areaRng[1]
                ]
            )
        if iscrowd:
            ids = [ann["id"] for ann in anns if ann["iscrowd"] == iscrowd]
        else:
            ids = [ann["id"] for ann in anns]
        return ids

    def getCatIds(self, catNms=[], supNms=[], catIds=[]):
        """
        filtering parameters. default skips that filter.
        :param catNms (str array)  : get cats for given cat names
        :param supNms (str array)  : get cats for given supercategory names
        :param catIds (int array)  : get cats for given cat ids
        :return: ids (int array)   : integer array of cat ids
        """
        catNms = catNms if self._is_array_like(catNms) else [catNms]
        supNms = supNms if self._is_array_like(supNms) else [supNms]
        catIds = catIds if self._is_array_like(catIds) else [catIds]

        if len(catNms) == len(supNms) == len(catIds) == 0:
            cats = self.dataset["categories"]
        else:
            cats = self.dataset["categories"]
            cats = (
                cats
                if len(catNms) == 0
                else [cat for cat in cats if cat["name"] in catNms]
            )
            cats = (
                cats
                if len(supNms) == 0
                else [cat for cat in cats if cat["supercategory"] in supNms]
            )
            cats = (
                cats
                if len(catIds) == 0
                else [cat for cat in cats if cat["id"] in catIds]
            )
        ids = [cat["id"] for cat in cats]
        return ids

    def getImgIds(self, imgIds=[], catIds=[]):
        """
        Get img ids that satisfy given filter conditions.
        :param imgIds (int array) : get imgs for given ids
        :param catIds (int array) : get imgs with all given cats
        :return: ids (int array)  : integer array of img ids
        """
        imgIds = imgIds if self._is_array_like(imgIds) else [imgIds]
        catIds = catIds if self._is_array_like(catIds) else [catIds]

        if len(imgIds) == len(catIds) == 0:
            ids = self.imgs.keys()
        else:
            ids = set(imgIds)
            for i, catId in enumerate(catIds):
                if i == 0 and len(ids) == 0:
                    ids = set(self.catToImgs[catId])
                else:
                    ids &= set(self.catToImgs[catId])
        return list(ids)

    def loadAnns(self, ids=[]):
        """
        Load anns with the specified ids.
        :param ids (int array)       : integer ids specifying anns
        :return: anns (object array) : loaded ann objects
        """
        if self._is_array_like(ids):
            return [self.anns[id] for id in ids]
        elif isinstance(ids, int):
            return [self.anns[ids]]

    def loadCats(self, ids=[]):
        """
        Load cats with the specified ids.
        :param ids (int array)       : integer ids specifying cats
        :return: cats (object array) : loaded cat objects
        """
        if self._is_array_like(ids):
            return [self.cats[id] for id in ids]
        elif isinstance(ids, int):
            return [self.cats[ids]]

    def loadImgs(self, ids=[]):
        """
        Load anns with the specified ids.
        :param ids (int array)       : integer ids specifying img
        :return: imgs (object array) : loaded img objects
        """
        if self._is_array_like(ids):
            return [self.imgs[id] for id in ids]
        elif isinstance(ids, int):
            return [self.imgs[ids]]


class DatasetUploadHandler(COCO):
    def get_img_bbox_payload(self, anns):
        predicted_classes = set()
        bboxes = []
        for ann in anns:
            bbox = ann["bbox"]
            bboxes.append(
                {
                    "point": [
                        [bbox[0], bbox[1]],
                        [bbox[0] + bbox[2], bbox[1]],
                        [bbox[0] + bbox[2], bbox[1] + bbox[3]],
                        [bbox[0], bbox[1] + bbox[3]],
                    ],
                    "class": self.original_category_referecences.get(
                        ann["category_id"]
                    ),
                    "recognition": ann.get("recognition", ""),
                }
            )
            predicted_classes.add(
                self.original_category_referecences.get(ann["category_id"])
            )
        return json.dumps(
            {
                "bboxes": [bboxes],
                "predicted_classes": list(predicted_classes),
                "classes": self.classes,
            }
        )

    def get_img_semantic_segmentation_payload(self, anns):
        predicted_classes = set()
        annotations = []
        for ann in anns:
            annotations.append(
                {
                    "segmentation": ann["segmentation"],
                    "category_id": self.original_category_referecences.get(
                        ann["category_id"]
                    ),
                }
            )
            predicted_classes.add(
                self.original_category_referecences.get(ann["category_id"])
            )
        return json.dumps(
            {
                "annotations": annotations,
                "predicted_classes": list(predicted_classes),
                "classes": self.classes,
            }
        )

    def get_img_instance_segmentation_payload(self, anns):
        return self.get_img_semantic_segmentation_payload(anns)

    def get_img_polygon_payload(self, anns):
        return self.get_img_semantic_segmentation_payload(anns)

    def get_img_line_payload(self, anns):
        return self.get_img_semantic_segmentation_payload(anns)

    def get_img_point_payload(self, anns):
        return self.get_img_semantic_segmentation_payload(anns)

    def get_payload(self, img_id):
        image = self.imgs[img_id]
        ann_ids = self.getAnnIds(imgIds=img_id)
        anns = self.loadAnns(ann_ids)
        if not os.path.isfile(os.path.join(self.data_path, image["file_name"])):
            logger.warning(
                "Image file not found: {}".format(
                    os.path.join(self.data_path, image["file_name"])
                )
            )
            return
        if len(anns) == 0:
            logger.warning("No annotations found for image: {}".format(img_id))
            return
        return getattr(self, f"get_{self.annotation_type}_payload")(anns)

    async def upload_image(self, session, url, image_id):
        image = self.loadImgs(image_id)[0]
        file_name = image["file_name"]
        payload = self.get_payload(image_id)
        if payload:
            async with aiofiles.open(
                os.path.join(self.data_path, file_name), "rb"
            ) as f:
                form_data = aiohttp.FormData()
                form_data.add_field("file", await f.read(), filename=file_name)
                form_data.add_field("result", self.get_payload(image_id))
                try:
                    # rate limiting
                    await asyncio.sleep(0.1)
                    async with session.post(url, data=form_data) as response:
                        if response.status == 403:
                            raise SubscriptionError(
                                "You have reached the maximum number of datasources for your subscription."
                            )
                        elif response.status == 400:
                            logger.error(await response.text())
                            return 0
                        response.raise_for_status()
                        return 1
                except SubscriptionError as e:
                    raise e
                except Exception as e:
                    logger.error(f"Error uploading file {file_name} - {e}")
        return 0
