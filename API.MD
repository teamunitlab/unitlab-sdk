Documentation for UnitLab AI APIs:

BASE URL: https://api.unitlab.ai/ocr/

## Authentication
Authentication is required to access the api.unitlab.ai. You can authenticate by including your API key in the header of your requests, you can get the api-key in app.unitlab.ai/UnitlabAI/api-keys:

Authorization: Api-Key YOUR_COMPANY_API_KEY

## API Endpoints

1. Digitization.
  1.1. Education OCR:
    PURPOSE: By using Education OCR, educators can quickly scan and convert printed materials into digital text, which can then be edited, annotated, and shared digitally. 

    REQUEST POST BASE_URL + 'education/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/education.webp",
      }
    
    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/education/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/education.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }

  1.2. Text Detection:
    PURPOSE: The Text Detection is to identify and locate text in images. Text detection is an important component of many computer vision applications, such as document scanning, content analysis, and image recognition. The primary goal of text detection is to extract meaningful information from visual representations that contain textual content, such as books, magazines, and advertisements.

    REQUEST POST BASE_URL + 'text-detection/':
      { 
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/text.jpeg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/text-detection/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/text.jpeg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.3. Math Script Identification:
    PURPOSE: The Math Script Identification is to recognize and identify mathematical expressions, formulas, and symbols in digital documents. This is a specialized form of text recognition that focuses on identifying mathematical notations, which can be challenging due to the complexity and variety of symbols and formulas used in mathematics.

    REQUEST POST BASE_URL + 'math-script/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/mathh_zhdONmC.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/math-script/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/mathh_zhdONmC.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }

  
  1.4. Language Script Identification:
    PURPOSE: The Language Script Identification is to automatically recognize and identify the written script or language used in a given text or document and
    it can be used such as developing text-to-speech systems that can correctly pronounce words and sentences in different languages and so on.


    REQUEST POST BASE_URL + 'language-script/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/language.png",
      }
    
    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/language-script/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/language.png",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }
    

  1.5. Fintech OCR:
    PURPOSE: The Fintech OCR is to improve the accuracy and efficiency of processing financial documents, such as invoices, receipts, bank statements, and checks. OCR technology can be used to convert these documents into machine-readable digital formats, making them easier to analyze and integrate with other financial systems.

    REQUEST POST BASE_URL + 'fintech/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/fintech3.jpeg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/fintech/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/fintech3.jpeg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.6. General OCR:
    PURPOSE: The General OCR technology has a wide range of applications, such as digitizing historical and cultural documents, improving the accessibility of information for people with visual impairments, automating data entry and document management systems, and enhancing the efficiency of business processes. 

    REQUEST POST BASE_URL + 'general/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/generaltest.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/general/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/generaltest.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }
    

  1.7. Document OCR:
    PURPOSE: The primary goal of Document OCR is to automate the process of data entry and document management, making it faster and more accurate. By converting documents into digital formats, businesses can easily search and analyze large volumes of documents, reducing manual effort and increasing productivity.

    REQUEST POST BASE_URL + 'document/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/doc2.webp",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/document/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/doc2.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }

  
  1.8. Base Segmentation:
    PURPOSE: The main goal of base segmentation in AI is to extract meaningful features from images, which can be used as inputs for various machine learning algorithms. By dividing an image into segments, each segment can be analyzed separately, and features such as color, texture, and shape can be extracted and used to identify and classify objects within the image.

    REQUEST POST BASE_URL + 'base-segmentation/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street.webp",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/base-segmentation/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }
    

  1.9. People Detection:
    PURPOSE: The main goal of people detection in AI is to accurately identify and locate people within an image or video stream, regardless of their position, orientation, or size. This is typically achieved by using object detection algorithms, which analyze the image and identify regions that contain human-like features or shapes.

    REQUEST POST BASE_URL + 'people/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/pee.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/people/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/pee.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.10. Car Detection:
    PURPOSE: The aim of car detection in AI is to automatically detect and locate cars within an image or video stream. Car detection is a fundamental project in computer vision and has numerous applications, such as traffic monitoring, parking lot management, and autonomous driving.

    REQUEST POST BASE_URL + 'car/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/e2c9fba2-ffa4826f815341a3a9771ccda797b47d.jpg",
      }
    
    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/car/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/e2c9fba2-ffa4826f815341a3a9771ccda797b47d.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.11. General Detection:
    PURPOSE: The aim of general detection in AI is to automatically detect and locate objects within an image or video stream, regardless of their class or category. General detection is a fundamental project in computer vision and has numerous applications, such as object recognition, scene understanding, and robotics.

    REQUEST POST BASE_URL + 'general-detection/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/gendec.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/general-detection/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/gendec.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }

  
  1.12. Car Detection System:
    PURPOSE: The main goal of a car detection system is to accurately identify and locate cars within an image or video stream, regardless of their orientation, size, or position within the frame. This is typically achieved using object detection algorithms, which analyze the image and identify regions that contain car-like features or shapes.

    REQUEST POST BASE_URL + 'car-detection/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/2dc39285-6ab2dbc328d84322a78544f2950699c8.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/car-detection/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/2dc39285-6ab2dbc328d84322a78544f2950699c8.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.13. Car Segmentation:
    PURPOSE: The aim of car segmentation polygons is to accurately identify and isolate the boundaries of cars in images using polygons.

    REQUEST POST BASE_URL + 'car-segmentation/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/cars.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/car-segmentation/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/2dc39285-6ab2dbc328d84322a78544f2950699c8.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.14. Person Segmentation:
    PURPOSE: The main goal of a Person Segmentation is to accurately identify and isolate the boundaries of people in images using polygons.

    REQUEST POST BASE_URL + 'person-segmentation/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/1e0e2879-eb87157d5544410fb89ee7ccd937d2b3.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/person-segmentation/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/1e0e2879-eb87157d5544410fb89ee7ccd937d2b3.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.15. Object Segmentation:
    PURPOSE: The main goal of a Object Segmentation is to accurately identify and isolate the boundaries of objects in images using polygons.

    REQUEST POST BASE_URL + 'object-segmentation/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/object-segmentation/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.16. Base Multikeypoint:
    PURPOSE: Base multikeypoint is a technique used in computer vision and machine learning for feature detection and extraction in images. The aim of base multikeypoint is to identify distinctive features, or keypoints, in an image that can be used to describe and match that image with other images.

    REQUEST POST BASE_URL + 'base-multikeypoint/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/base-multikeypoint/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


  1.17. Object Classification:
    PURPOSE: The Object classification in AI refers to the process of identifying the category or class of an object in an image or video frame. It involves analyzing the visual features of an object and comparing them to a set of predefined categories or classes. The AI system learns to recognize the visual patterns or features that are common to each category and can then use these patterns to classify new objects.

    REQUEST POST BASE_URL + 'object-classification/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/object-classification/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/street_Ej7YL6e.webp",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }
   

2. Industry.
  2.1. Retail Store:
    PURPOSE: The aim of using AI in retail stores is to provide a better customer experience, increase sales, and optimize store operations. AI can help retailers better understand their customers, improve their operations, and stay ahead of the competition.

    REQUEST POST BASE_URL + 'retail-store/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/retail.png",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/retail-store/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/retail.png",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


3. E-Commerce.
  3.1. Fashion Detection:
    PURPOSE: The Fashion detection systems use computer vision algorithms to analyze images and identify specific fashion items, such as dresses, pants, shoes, and accessories. These systems can be trained on large datasets of fashion images, enabling them to recognize different styles, colors, and patterns.

    REQUEST POST BASE_URL + 'fashion/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/shohcomp-84bb57ec/taskimage/Group_625147.png",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/fashion/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/shohcomp-84bb57ec/taskimage/Group_625147.png",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


4. Agriculture:
  4.1. Fruit Detection:
    PURPOSE: The Fruit detection systems use image processing algorithms to analyze images of fruit trees and identify the fruits based on their size, shape, color, and texture. These systems can help farmers identify ripe fruits that are ready for harvesting, reducing the time and labor required for manual inspection.

    REQUEST POST BASE_URL + 'fruit/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/fruit.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/fruit/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/fruit.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }


5. Health:
  5.1. Red Blood Cell:
    PURPOSE: This one can be used to develop algorithms that analyze digital images of blood samples and automatically detect and classify different types of red blood cells, including abnormal cells that may indicate the presence of a blood disorder. These algorithms can improve the accuracy and speed of blood cell analysis, allowing for earlier and more precise diagnoses.

    REQUEST POST BASE_URL + 'red-blood-cell/':
      {
        "image_url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/00f4a8b3-8fb27f7db21f494697975a034c8cc93b.jpg",
      }

    For backward compatibility purposes, users can also submit a JSON body with the image's
    base64 encoding in the image_url field.
    curl -X POST https://api.unitlab.ai/ocr/red-blood-cell/ -H 'Api-Key: API_KEY'

    RESPONSE:
    The boxes field consists of the results of recognized outputs with:
    box, recognition, class, text_recognition_confs, who_labeled, who_reviewed and boxtype.
      { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/00f4a8b3-8fb27f7db21f494697975a034c8cc93b.jpg",
        "output":[
          "boxes": [
            {}
          ],
          "meta": [
          ],
        ],
        "status": "labeled",
        "review_status": ""
      }